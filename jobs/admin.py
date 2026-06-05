from django.contrib import admin

from .models import Company, Post, Technology, TechnologyAlias, TechnologyMapping, Title


@admin.register(TechnologyAlias)
class TechnologyAliasAdmin(admin.ModelAdmin):
    list_display = ("alias", "technology", "source", "created")
    list_select_related = ("technology",)
    search_fields = ("alias", "normalized_alias", "technology__name")


admin.site.register(Post)
admin.site.register(Technology)
admin.site.register(TechnologyMapping)
admin.site.register(Title)
admin.site.register(Company)
