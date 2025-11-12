from django.contrib import admin

from .models import Company, Email, EmailSent, Post, Technology, Title

admin.site.register(Post)
admin.site.register(Technology)
admin.site.register(Title)
admin.site.register(Company)
admin.site.register(Email)
admin.site.register(EmailSent)
