from django.http import HttpResponse


def home(request):
    return HttpResponse("multiWdg backend is running")
