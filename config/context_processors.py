import os

def export_vars(request):
    return {
        'GOOGLE_MAPS_API_KEY': os.environ.get('GOOGLE_MAPS_API_KEY')
    }