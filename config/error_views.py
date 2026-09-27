from django.shortcuts import render


def error_403(request, exception=None):
    return render(request, "403.html", {
        "error_code": "403",
        "error_title": "Access Denied",
        "error_message": "You don’t have permission to access this page.",
    }, status=403)


def error_404(request, exception=None):
    return render(request, "404.html", {
        "error_code": "404",
        "error_title": "Page Not Found",
        "error_message": "The page you’re looking for doesn’t exist or may have moved.",
    }, status=404)


def error_500(request):
    return render(request, "500.html", {
        "error_code": "500",
        "error_title": "Something Went Wrong",
        "error_message": "We couldn’t complete your request. Please try again.",
    }, status=500)
