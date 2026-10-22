import base64
import hashlib
from datetime import timedelta
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone


AUTHORIZATION_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
ACCOUNTING_SCOPE = "com.intuit.quickbooks.accounting"
TOKEN_REFRESH_MARGIN = timedelta(minutes=5)
MINOR_VERSION = "75"
EXPENSE_ACCOUNT_TYPES = {"Expense", "Other Expense", "Cost of Goods Sold"}
PAYMENT_ACCOUNT_TYPES = {"Bank", "Credit Card"}


class QuickBooksConfigurationError(ImproperlyConfigured):
    pass


class QuickBooksAPIError(Exception):
    pass


def configuration():
    values = {
        "client_id": getattr(settings, "QUICKBOOKS_CLIENT_ID", ""),
        "client_secret": getattr(settings, "QUICKBOOKS_CLIENT_SECRET", ""),
        "redirect_uri": getattr(settings, "QUICKBOOKS_REDIRECT_URI", ""),
        "environment": getattr(settings, "QUICKBOOKS_ENVIRONMENT", "sandbox"),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise QuickBooksConfigurationError(
            "Missing QuickBooks configuration: " + ", ".join(missing)
        )
    if values["environment"] not in {"sandbox", "production"}:
        raise QuickBooksConfigurationError("QUICKBOOKS_ENVIRONMENT must be sandbox or production.")
    return values


def authorization_url(state):
    config = configuration()
    return AUTHORIZATION_URL + "?" + urlencode({
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": ACCOUNTING_SCOPE,
        "state": state,
    })


def exchange_authorization_code(code):
    config = configuration()
    response = requests.post(
        TOKEN_URL,
        auth=(config["client_id"], config["client_secret"]),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect_uri"],
        },
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if not response.ok:
        raise QuickBooksAPIError("QuickBooks authorization failed. Please reconnect and try again.")
    return response.json()


def refresh_access_token(refresh_token):
    config = configuration()
    response = requests.post(
        TOKEN_URL,
        auth=(config["client_id"], config["client_secret"]),
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if not response.ok:
        raise QuickBooksAPIError(
            "QuickBooks authorization expired or could not be refreshed. Please reconnect."
        )
    return response.json()


def company_info(realm_id, access_token, environment):
    base = "https://sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "https://quickbooks.api.intuit.com"
    response = requests.get(
        f"{base}/v3/company/{realm_id}/companyinfo/{realm_id}",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        params={"minorversion": "75"},
        timeout=20,
    )
    if not response.ok:
        raise QuickBooksAPIError("COL360 connected, but QuickBooks company details could not be verified.")
    return response.json().get("CompanyInfo", {})


def _api_base(environment):
    if environment == "sandbox":
        return "https://sandbox-quickbooks.api.intuit.com"
    return "https://quickbooks.api.intuit.com"


def _response_error(response, fallback):
    try:
        payload = response.json()
        errors = payload.get("Fault", {}).get("Error", [])
        if errors:
            detail = errors[0].get("Detail") or errors[0].get("Message")
            if detail:
                return f"{fallback}: {detail}"
    except (TypeError, ValueError):
        pass
    return fallback


@transaction.atomic
def refresh_connection(connection, force=False):
    from .models import QuickBooksConnection

    connection = QuickBooksConnection.objects.select_for_update().get(pk=connection.pk)
    if not force and connection.access_token_expires_at > timezone.now() + TOKEN_REFRESH_MARGIN:
        return connection
    try:
        current_refresh_token = decrypt_token(connection.refresh_token_encrypted)
        payload = refresh_access_token(current_refresh_token)
        access_token = payload["access_token"]
        rotated_refresh_token = payload.get("refresh_token") or current_refresh_token
        access_expiry, refresh_expiry = token_expiries(payload)
    except (KeyError, QuickBooksAPIError) as exc:
        connection.last_error = str(exc)
        connection.save(update_fields=["last_error", "updated_at"])
        raise QuickBooksAPIError(str(exc)) from exc

    connection.access_token_encrypted = encrypt_token(access_token)
    connection.refresh_token_encrypted = encrypt_token(rotated_refresh_token)
    connection.access_token_expires_at = access_expiry
    if refresh_expiry is not None:
        connection.refresh_token_expires_at = refresh_expiry
    connection.last_error = ""
    connection.save(update_fields=[
        "access_token_encrypted",
        "refresh_token_encrypted",
        "access_token_expires_at",
        "refresh_token_expires_at",
        "last_error",
        "updated_at",
    ])
    return connection


def quickbooks_request(connection, method, path, *, params=None, json=None):
    connection = refresh_connection(connection)
    url = f"{_api_base(connection.environment)}{path}"
    for attempt in range(2):
        response = requests.request(
            method,
            url,
            headers={
                "Authorization": f"Bearer {decrypt_token(connection.access_token_encrypted)}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            params=params,
            json=json,
            timeout=20,
        )
        if response.status_code != 401 or attempt:
            break
        connection = refresh_connection(connection, force=True)
    if not response.ok:
        raise QuickBooksAPIError(_response_error(response, "QuickBooks request failed"))
    try:
        return response.json()
    except ValueError as exc:
        raise QuickBooksAPIError("QuickBooks returned an unreadable response.") from exc


def test_connection(connection):
    payload = quickbooks_request(
        connection,
        "GET",
        f"/v3/company/{connection.realm_id}/companyinfo/{connection.realm_id}",
        params={"minorversion": MINOR_VERSION},
    )
    info = payload.get("CompanyInfo", {})
    connection.company_name = info.get("CompanyName") or connection.company_name
    connection.last_synced_at = timezone.now()
    connection.last_error = ""
    connection.save(update_fields=["company_name", "last_synced_at", "last_error", "updated_at"])
    return info


def _vendor_display_name(vendor):
    return (vendor.company_name or vendor.name).strip()


def _quoted_query_value(value):
    return value.replace("\\", "\\\\").replace("'", "\\'")


@transaction.atomic
def sync_vendor(connection, vendor):
    from .models import QuickBooksConnection, QuickBooksVendorMapping

    # Serialize sync attempts for this company so two staff requests cannot
    # both pass the remote-name check and create the same vendor.
    connection = QuickBooksConnection.objects.select_for_update().get(pk=connection.pk)

    mapping = QuickBooksVendorMapping.objects.filter(
        connection=connection, vendor=vendor
    ).first()
    if mapping:
        payload = quickbooks_request(
            connection,
            "GET",
            f"/v3/company/{connection.realm_id}/vendor/{mapping.quickbooks_vendor_id}",
            params={"minorversion": MINOR_VERSION},
        )
        remote_vendor = payload.get("Vendor", {})
    else:
        display_name = _vendor_display_name(vendor)
        query = "select * from Vendor where DisplayName = '{}'".format(
            _quoted_query_value(display_name)
        )
        payload = quickbooks_request(
            connection,
            "GET",
            f"/v3/company/{connection.realm_id}/query",
            params={"query": query, "minorversion": MINOR_VERSION},
        )
        matches = payload.get("QueryResponse", {}).get("Vendor", [])
        if len(matches) > 1:
            raise QuickBooksAPIError(
                "More than one QuickBooks vendor has this display name. Resolve the duplicates in QuickBooks before syncing."
            )
        if matches:
            remote_vendor = matches[0]
        else:
            vendor_payload = {"DisplayName": display_name}
            if vendor.company_name:
                vendor_payload["CompanyName"] = vendor.company_name
            if vendor.email:
                vendor_payload["PrimaryEmailAddr"] = {"Address": vendor.email}
            if vendor.phone:
                vendor_payload["PrimaryPhone"] = {"FreeFormNumber": vendor.phone}
            created = quickbooks_request(
                connection,
                "POST",
                f"/v3/company/{connection.realm_id}/vendor",
                params={"minorversion": MINOR_VERSION},
                json=vendor_payload,
            )
            remote_vendor = created.get("Vendor", {})

    remote_id = str(remote_vendor.get("Id", ""))
    if not remote_id:
        raise QuickBooksAPIError("QuickBooks did not return a vendor ID.")
    now = timezone.now()
    mapping, _ = QuickBooksVendorMapping.objects.update_or_create(
        connection=connection,
        vendor=vendor,
        defaults={
            "quickbooks_vendor_id": remote_id,
            "sync_token": str(remote_vendor.get("SyncToken", "")),
            "display_name": remote_vendor.get("DisplayName") or _vendor_display_name(vendor),
            "last_synced_at": now,
            "last_error": "",
        },
    )
    connection.last_synced_at = now
    connection.last_error = ""
    connection.save(update_fields=["last_synced_at", "last_error", "updated_at"])
    return mapping


def list_expense_accounts(connection):
    payload = quickbooks_request(
        connection,
        "GET",
        f"/v3/company/{connection.realm_id}/query",
        params={
            "query": "select * from Account where Active = true maxresults 1000",
            "minorversion": MINOR_VERSION,
        },
    )
    accounts = payload.get("QueryResponse", {}).get("Account", [])
    return sorted(
        [
            account
            for account in accounts
            if account.get("Active", True)
            and account.get("AccountType") in EXPENSE_ACCOUNT_TYPES
        ],
        key=lambda account: (
            account.get("FullyQualifiedName") or account.get("Name") or ""
        ).lower(),
    )


def list_payment_accounts(connection):
    payload = quickbooks_request(
        connection,
        "GET",
        f"/v3/company/{connection.realm_id}/query",
        params={
            "query": "select * from Account where Active = true maxresults 1000",
            "minorversion": MINOR_VERSION,
        },
    )
    accounts = payload.get("QueryResponse", {}).get("Account", [])
    return sorted(
        [
            account
            for account in accounts
            if account.get("Active", True)
            and account.get("AccountType") in PAYMENT_ACCOUNT_TYPES
        ],
        key=lambda account: (
            account.get("AccountType", ""),
            (account.get("FullyQualifiedName") or account.get("Name") or "").lower(),
        ),
    )


def _expense_account(connection, account_id):
    if not str(account_id).isdigit():
        raise QuickBooksAPIError("Select a valid QuickBooks expense account.")
    payload = quickbooks_request(
        connection,
        "GET",
        f"/v3/company/{connection.realm_id}/account/{account_id}",
        params={"minorversion": MINOR_VERSION},
    )
    account = payload.get("Account", {})
    if (
        str(account.get("Id", "")) != str(account_id)
        or not account.get("Active", True)
        or account.get("AccountType") not in EXPENSE_ACCOUNT_TYPES
    ):
        raise QuickBooksAPIError("Select an active QuickBooks expense account.")
    return account


def _payment_account(connection, account_id, payment_method):
    if not str(account_id).isdigit():
        raise QuickBooksAPIError("Select a valid QuickBooks payment account.")
    payload = quickbooks_request(
        connection,
        "GET",
        f"/v3/company/{connection.realm_id}/account/{account_id}",
        params={"minorversion": MINOR_VERSION},
    )
    account = payload.get("Account", {})
    account_type = account.get("AccountType")
    expected_type = "Credit Card" if payment_method == "card" else "Bank"
    if (
        str(account.get("Id", "")) != str(account_id)
        or not account.get("Active", True)
        or account_type != expected_type
    ):
        raise QuickBooksAPIError(
            f"Select an active QuickBooks {expected_type.lower()} account for this payment method."
        )
    return account


def bill_document_number(invoice):
    return invoice.invoice_number.strip() if invoice.invoice_number else f"COL360-WO-{invoice.work_order_id}"


@transaction.atomic
def sync_bill(connection, invoice, expense_account_id):
    from maintenance.models import VendorInvoice
    from .models import QuickBooksBillMapping, QuickBooksConnection

    connection = QuickBooksConnection.objects.select_for_update().get(pk=connection.pk)
    invoice = VendorInvoice.objects.select_for_update().select_related(
        "vendor", "work_order__unit__property"
    ).get(pk=invoice.pk)
    if invoice.status != "approved":
        raise QuickBooksAPIError(
            "Only an approved, unpaid invoice can be synchronized as a QuickBooks bill."
        )
    if invoice.amount <= 0:
        raise QuickBooksAPIError("The invoice total must be greater than zero.")
    if not invoice.invoice_date or not invoice.due_date:
        raise QuickBooksAPIError(
            "Invoice date and due date are required before QuickBooks synchronization."
        )

    existing_mapping = QuickBooksBillMapping.objects.select_related("connection").filter(
        invoice=invoice
    ).first()
    if existing_mapping:
        if existing_mapping.connection_id != connection.pk:
            raise QuickBooksAPIError(
                "This invoice was synchronized to a different QuickBooks company. Review it before reconnecting or resyncing."
            )
        payload = quickbooks_request(
            connection,
            "GET",
            f"/v3/company/{connection.realm_id}/bill/{existing_mapping.quickbooks_bill_id}",
            params={"minorversion": MINOR_VERSION},
        )
        remote_bill = payload.get("Bill", {})
        if not remote_bill.get("Id"):
            raise QuickBooksAPIError("The mapped QuickBooks bill could not be verified.")
        existing_mapping.sync_token = str(remote_bill.get("SyncToken", ""))
        now = timezone.now()
        existing_mapping.last_synced_at = now
        existing_mapping.last_error = ""
        existing_mapping.save(update_fields=[
            "sync_token", "last_synced_at", "last_error", "updated_at"
        ])
        connection.last_synced_at = now
        connection.last_error = ""
        connection.save(update_fields=["last_synced_at", "last_error", "updated_at"])
        return existing_mapping

    account = _expense_account(connection, expense_account_id)
    vendor_mapping = sync_vendor(connection, invoice.vendor)
    document_number = bill_document_number(invoice)
    query = "select * from Bill where DocNumber = '{}'".format(
        _quoted_query_value(document_number)
    )
    payload = quickbooks_request(
        connection,
        "GET",
        f"/v3/company/{connection.realm_id}/query",
        params={"query": query, "minorversion": MINOR_VERSION},
    )
    matches = [
        bill
        for bill in payload.get("QueryResponse", {}).get("Bill", [])
        if str(bill.get("VendorRef", {}).get("value", ""))
        == vendor_mapping.quickbooks_vendor_id
    ]
    if len(matches) > 1:
        raise QuickBooksAPIError(
            "Multiple QuickBooks bills match this vendor and invoice number. Resolve the duplicates in QuickBooks before syncing."
        )
    if matches:
        remote_bill = matches[0]
    else:
        property_label = invoice.work_order.unit.property.street_address
        if invoice.work_order.unit.unit_number:
            property_label += f" · Unit {invoice.work_order.unit.unit_number}"
        bill_payload = {
            "VendorRef": {"value": vendor_mapping.quickbooks_vendor_id},
            "TxnDate": invoice.invoice_date.isoformat(),
            "DueDate": invoice.due_date.isoformat(),
            "DocNumber": document_number,
            "PrivateNote": f"COL360 Work Order #{invoice.work_order_id} · {property_label}"[:4000],
            "Line": [{
                "Amount": float(invoice.amount),
                "DetailType": "AccountBasedExpenseLineDetail",
                "Description": invoice.work_order.title[:4000],
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {
                        "value": str(account["Id"]),
                        "name": account.get("FullyQualifiedName") or account.get("Name", ""),
                    }
                },
            }],
        }
        created = quickbooks_request(
            connection,
            "POST",
            f"/v3/company/{connection.realm_id}/bill",
            params={"minorversion": MINOR_VERSION},
            json=bill_payload,
        )
        remote_bill = created.get("Bill", {})

    remote_id = str(remote_bill.get("Id", ""))
    if not remote_id:
        raise QuickBooksAPIError("QuickBooks did not return a bill ID.")
    now = timezone.now()
    mapping = QuickBooksBillMapping.objects.create(
        connection=connection,
        invoice=invoice,
        quickbooks_bill_id=remote_id,
        sync_token=str(remote_bill.get("SyncToken", "")),
        document_number=document_number,
        expense_account_id=str(account["Id"]),
        expense_account_name=account.get("FullyQualifiedName") or account.get("Name", ""),
        last_synced_at=now,
    )
    connection.last_synced_at = now
    connection.last_error = ""
    connection.save(update_fields=["last_synced_at", "last_error", "updated_at"])
    return mapping


def payment_document_number(payment):
    return f"COL360-PAY-{payment.pk}"


def _remote_payment(connection, quickbooks_payment_id):
    payload = quickbooks_request(
        connection,
        "GET",
        f"/v3/company/{connection.realm_id}/billpayment/{quickbooks_payment_id}",
        params={"minorversion": MINOR_VERSION},
    )
    return payload.get("BillPayment", {})


def sync_bill_payment(connection, payment, payment_account_id):
    from maintenance.models import VendorPayment
    from .models import (
        QuickBooksBillMapping,
        QuickBooksConnection,
        QuickBooksPaymentMapping,
    )

    with transaction.atomic():
        connection = QuickBooksConnection.objects.select_for_update().get(pk=connection.pk)
        payment = VendorPayment.objects.select_for_update().select_related(
            "invoice__vendor", "invoice__work_order"
        ).get(pk=payment.pk)
        if payment.status != "recorded":
            raise QuickBooksAPIError("Only a recorded payment can be synchronized.")
        bill_mapping = QuickBooksBillMapping.objects.select_related("connection").filter(
            invoice=payment.invoice
        ).first()
        if not bill_mapping:
            raise QuickBooksAPIError(
                "Synchronize the approved invoice to QuickBooks before recording its payment."
            )
        if bill_mapping.connection_id != connection.pk:
            raise QuickBooksAPIError(
                "The bill belongs to a different QuickBooks company."
            )

        document_number = payment_document_number(payment)
        mapping, _ = QuickBooksPaymentMapping.objects.select_for_update().get_or_create(
            payment=payment,
            defaults={
                "connection": connection,
                "bill_mapping": bill_mapping,
                "document_number": document_number,
                "payment_account_id": str(payment_account_id),
                "payment_account_name": "",
                "payment_account_type": "",
            },
        )
        if mapping.connection_id != connection.pk:
            raise QuickBooksAPIError(
                "This payment was synchronized to a different QuickBooks company."
            )
        if mapping.status == "deleted":
            raise QuickBooksAPIError("A voided QuickBooks payment cannot be synchronized again.")

        try:
            account = _payment_account(
                connection, payment_account_id, payment.payment_method
            )
            if mapping.quickbooks_payment_id:
                remote_payment = _remote_payment(connection, mapping.quickbooks_payment_id)
            else:
                vendor_mapping = sync_vendor(connection, payment.invoice.vendor)
                query = "select * from BillPayment where DocNumber = '{}'".format(
                    _quoted_query_value(document_number)
                )
                payload = quickbooks_request(
                    connection,
                    "GET",
                    f"/v3/company/{connection.realm_id}/query",
                    params={"query": query, "minorversion": MINOR_VERSION},
                )
                matches = [
                    remote
                    for remote in payload.get("QueryResponse", {}).get("BillPayment", [])
                    if str(remote.get("VendorRef", {}).get("value", ""))
                    == vendor_mapping.quickbooks_vendor_id
                ]
                if len(matches) > 1:
                    raise QuickBooksAPIError(
                        "Multiple QuickBooks payments match this COL360 payment. Resolve the duplicates in QuickBooks."
                    )
                if matches:
                    remote_payment = matches[0]
                else:
                    account_ref = {
                        "value": str(account["Id"]),
                        "name": account.get("FullyQualifiedName") or account.get("Name", ""),
                    }
                    payment_payload = {
                        "VendorRef": {"value": vendor_mapping.quickbooks_vendor_id},
                        "TxnDate": payment.payment_date.isoformat(),
                        "TotalAmt": float(payment.amount),
                        "DocNumber": document_number,
                        "PrivateNote": (
                            f"COL360 payment #{payment.pk} for invoice "
                            f"{payment.invoice.invoice_number or payment.invoice_id}"
                        )[:4000],
                        "Line": [{
                            "Amount": float(payment.amount),
                            "LinkedTxn": [{
                                "TxnId": bill_mapping.quickbooks_bill_id,
                                "TxnType": "Bill",
                            }],
                        }],
                    }
                    if account.get("AccountType") == "Credit Card":
                        payment_payload.update({
                            "PayType": "CreditCard",
                            "CreditCardPayment": {"CCAccountRef": account_ref},
                        })
                    else:
                        payment_payload.update({
                            "PayType": "Check",
                            "CheckPayment": {"BankAccountRef": account_ref},
                        })
                    created = quickbooks_request(
                        connection,
                        "POST",
                        f"/v3/company/{connection.realm_id}/billpayment",
                        params={"minorversion": MINOR_VERSION},
                        json=payment_payload,
                    )
                    remote_payment = created.get("BillPayment", {})

            remote_id = str(remote_payment.get("Id", ""))
            if not remote_id:
                raise QuickBooksAPIError("QuickBooks did not return a bill payment ID.")
        except (QuickBooksAPIError, QuickBooksConfigurationError) as exc:
            mapping.status = "error"
            mapping.last_error = str(exc)
            mapping.save(update_fields=["status", "last_error", "updated_at"])
            error = exc
        else:
            now = timezone.now()
            mapping.quickbooks_payment_id = remote_id
            mapping.sync_token = str(remote_payment.get("SyncToken", ""))
            mapping.document_number = document_number
            mapping.payment_account_id = str(account["Id"])
            mapping.payment_account_name = account.get("FullyQualifiedName") or account.get("Name", "")
            mapping.payment_account_type = account.get("AccountType", "")
            mapping.status = "synced"
            mapping.last_synced_at = now
            mapping.last_error = ""
            mapping.save()
            connection.last_synced_at = now
            connection.last_error = ""
            connection.save(update_fields=["last_synced_at", "last_error", "updated_at"])
            error = None

    if error:
        raise QuickBooksAPIError(str(error))
    return mapping


def delete_bill_payment(connection, payment):
    from .models import QuickBooksPaymentMapping

    with transaction.atomic():
        mapping = QuickBooksPaymentMapping.objects.select_for_update().select_related(
            "connection"
        ).filter(payment=payment).first()
        if not mapping or mapping.status == "deleted":
            return mapping
        if mapping.connection_id != connection.pk:
            raise QuickBooksAPIError(
                "This payment belongs to a different QuickBooks company."
            )
        try:
            remote_payment = _remote_payment(connection, mapping.quickbooks_payment_id)
            quickbooks_request(
                connection,
                "POST",
                f"/v3/company/{connection.realm_id}/billpayment",
                params={"operation": "delete", "minorversion": MINOR_VERSION},
                json={
                    "Id": mapping.quickbooks_payment_id,
                    "SyncToken": str(
                        remote_payment.get("SyncToken", mapping.sync_token)
                    ),
                },
            )
        except (QuickBooksAPIError, QuickBooksConfigurationError) as exc:
            mapping.status = "error"
            mapping.last_error = str(exc)
            mapping.save(update_fields=["status", "last_error", "updated_at"])
            error = exc
        else:
            mapping.status = "deleted"
            mapping.last_synced_at = timezone.now()
            mapping.last_error = ""
            mapping.save(update_fields=[
                "status", "last_synced_at", "last_error", "updated_at"
            ])
            error = None
    if error:
        raise QuickBooksAPIError(str(error))
    return mapping


def revoke_token(token):
    config = configuration()
    response = requests.post(
        REVOKE_URL,
        auth=(config["client_id"], config["client_secret"]),
        json={"token": token},
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if not response.ok:
        raise QuickBooksAPIError("QuickBooks could not be disconnected. Please try again.")


def _fernet():
    source = f"col360-quickbooks:{settings.SECRET_KEY}".encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(source).digest()))


def encrypt_token(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt_token(value):
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise QuickBooksAPIError("Stored QuickBooks credentials could not be decrypted.") from exc


def token_expiries(payload):
    now = timezone.now()
    access = now + timedelta(seconds=int(payload.get("expires_in", 3600)))
    refresh_seconds = payload.get("x_refresh_token_expires_in")
    refresh = now + timedelta(seconds=int(refresh_seconds)) if refresh_seconds else None
    return access, refresh
