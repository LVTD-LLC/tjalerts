from django.contrib import admin

from .models import Company, Post, Technology, TechnologyAlias, TechnologyMapping, Title

admin.site.register(Post)
admin.site.register(Technology)
admin.site.register(TechnologyAlias)
admin.site.register(TechnologyMapping)
admin.site.register(Title)
admin.site.register(Company)
