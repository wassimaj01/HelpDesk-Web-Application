from django.contrib import admin

from .models import (
    Lieu,
    LieuService,
    ProblemType,
    Service,
    Ticket,
    TicketHistory,
    UserProfile,
)


@admin.register(Lieu)
class LieuAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'is_active', 'created_at')
    list_filter = ('is_active', 'city')
    search_fields = ('name', 'city', 'address')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(LieuService)
class LieuServiceAdmin(admin.ModelAdmin):
    list_display = ('lieu', 'service', 'is_active', 'created_at')
    list_filter = ('is_active', 'lieu', 'service')
    search_fields = ('lieu__name', 'service__name', 'service__code')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('lieu', 'service')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'lieu_service', 'phone', 'is_active', 'created_at')
    list_filter = ('is_active', 'lieu_service__lieu', 'lieu_service__service')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user', 'lieu_service')


@admin.register(ProblemType)
class ProblemTypeAdmin(admin.ModelAdmin):
    list_display = ('label', 'category', 'responsible_admin', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'responsible_admin')
    search_fields = ('label', 'description')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('responsible_admin',)


class TicketHistoryInline(admin.TabularInline):
    model = TicketHistory
    extra = 0
    can_delete = False
    fields = (
        'action',
        'old_status',
        'new_status',
        'old_assigned_to',
        'new_assigned_to',
        'changed_by',
        'comment',
        'created_at',
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'problem_type',
        'category',
        'status',
        'created_by',
        'responsible_admin',
        'assigned_to',
        'created_at',
    )
    list_filter = ('status', 'category', 'admin_validation_decision', 'responsible_admin')
    search_fields = ('reference', 'description', 'created_by__username')
    autocomplete_fields = (
        'problem_type',
        'created_by',
        'requester_lieu_service',
        'responsible_admin',
        'assigned_to',
        'assigned_by',
        'resolved_by',
        'validated_by',
        'closed_by',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'assigned_at',
        'resolved_at',
        'validated_at',
        'closed_at',
    )
    inlines = [TicketHistoryInline]


@admin.register(TicketHistory)
class TicketHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'ticket',
        'action',
        'old_status',
        'new_status',
        'changed_by',
        'created_at',
    )
    list_filter = ('action', 'old_status', 'new_status')
    search_fields = ('ticket__reference', 'comment', 'changed_by__username')
    readonly_fields = (
        'ticket',
        'action',
        'old_status',
        'new_status',
        'old_assigned_to',
        'new_assigned_to',
        'changed_by',
        'comment',
        'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
