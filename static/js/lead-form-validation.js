document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("leadForm");
  if (!form) return;

  const nameInput = document.getElementById("id_name");
  const phoneInput = document.getElementById("id_phone");
  const emailInput = document.getElementById("id_email");

  const nameRegex = /^[A-Za-z]+(?:[ .'-][A-Za-z]+)*$/;
  const emailDomainRegex = /^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$/;

  function getOrCreateErrorList(input) {
    const field = input.closest(".cr-field");
    let list = field.querySelector(".cr-errorlist");
    if (!list) {
      list = document.createElement("ul");
      list.className = "cr-errorlist";
      field.appendChild(list);
    }
    return list;
  }

  function setFieldError(input, message) {
    const list = getOrCreateErrorList(input);
    list.innerHTML = "";

    if (message) {
      input.classList.add("is-invalid");
      const li = document.createElement("li");
      li.textContent = message;
      list.appendChild(li);
      return false;
    }

    input.classList.remove("is-invalid");
    return true;
  }

  function normalizePhone(value) {
    return (value || "").replace(/\D/g, "");
  }

  function formatPhone(value) {
    let digits = normalizePhone(value);

    if (digits.length === 11 && digits.startsWith("1")) {
      digits = digits.slice(1);
    }

    if (digits.length <= 3) return digits;
    if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
  }

  function validateName() {
    if (!nameInput) return true;
    const value = nameInput.value.trim();

    if (!value) return setFieldError(nameInput, "Name is required.");
    if (value.length < 2) return setFieldError(nameInput, "Name must be at least 2 characters long.");
    if (value.length > 120) return setFieldError(nameInput, "Name must be no more than 120 characters long.");
    if (!nameRegex.test(value)) {
      return setFieldError(
        nameInput,
        "Enter a valid name. Only letters, spaces, apostrophes, periods, and hyphens are allowed."
      );
    }

    return setFieldError(nameInput, "");
  }

  function validatePhone() {
    if (!phoneInput) return true;

    const raw = phoneInput.value.trim();
    if (!raw) return setFieldError(phoneInput, "");

    let digits = normalizePhone(raw);
    if (digits.length === 11 && digits.startsWith("1")) {
      digits = digits.slice(1);
    }

    if (digits.length !== 10) {
      return setFieldError(phoneInput, "Enter a valid US phone number.");
    }

    if (digits[0] === "0" || digits[0] === "1" || digits[3] === "0" || digits[3] === "1") {
      return setFieldError(phoneInput, "Enter a valid US phone number.");
    }

    return setFieldError(phoneInput, "");
  }

  function validateEmail() {
    if (!emailInput) return true;
    const value = emailInput.value.trim().toLowerCase();

    if (!value) return setFieldError(emailInput, "Email is required.");

    const simpleEmailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!simpleEmailPattern.test(value)) {
      return setFieldError(emailInput, "Enter a valid email address.");
    }

    const parts = value.split("@");
    if (parts.length !== 2) {
      return setFieldError(emailInput, "Enter a valid email address.");
    }

    const domain = parts[1];
    if (!emailDomainRegex.test(domain)) {
      return setFieldError(emailInput, "Enter a valid email domain.");
    }

    return setFieldError(emailInput, "");
  }

  if (nameInput) {
    nameInput.addEventListener("blur", validateName);
    nameInput.addEventListener("input", function () {
      if (nameInput.classList.contains("is-invalid")) validateName();
    });
  }

  if (phoneInput) {
    phoneInput.addEventListener("input", function () {
      phoneInput.value = formatPhone(phoneInput.value);
      if (phoneInput.classList.contains("is-invalid")) validatePhone();
    });
    phoneInput.addEventListener("blur", validatePhone);
  }

  if (emailInput) {
    emailInput.addEventListener("blur", validateEmail);
    emailInput.addEventListener("input", function () {
      if (emailInput.classList.contains("is-invalid")) validateEmail();
    });
  }

  form.addEventListener("submit", function (event) {
    const okName = validateName();
    const okPhone = validatePhone();
    const okEmail = validateEmail();

    if (!okName || !okPhone || !okEmail) {
      event.preventDefault();
    }
  });
});