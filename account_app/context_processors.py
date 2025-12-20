def display_name(request):
    if request.user.is_authenticated:
        name = request.user.username if request.user.username else request.user.email.split('@')[0]
        return {'display_name': name}
    return {'display_name': None}
