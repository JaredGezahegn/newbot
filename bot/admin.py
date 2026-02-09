from django.contrib import admin
from bot.models import User, Confession, Comment, Reaction, Feedback, UserInteraction
from bot.services.analytics_service import AnalyticsService


@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    """
    Admin interface for UserInteraction model.
    
    This admin interface is designed to preserve user privacy by:
    - Not displaying user identities directly
    - Showing only aggregate statistics
    - Limiting access to interaction details
    """
    list_display = ('id', 'user_id', 'interaction_type', 'timestamp')
    list_filter = ('interaction_type', 'timestamp')
    search_fields = ('interaction_type',)
    readonly_fields = ('user', 'interaction_type', 'timestamp')
    date_hierarchy = 'timestamp'
    
    # Disable add/change permissions to prevent manual manipulation
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    # Only allow viewing and deleting (for data retention)
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def changelist_view(self, request, extra_context=None):
        """
        Override changelist view to add privacy-preserving analytics summary.
        """
        extra_context = extra_context or {}
        
        # Add aggregate analytics to the context
        analytics_report = AnalyticsService.get_admin_analytics_report()
        extra_context['analytics_report'] = analytics_report
        
        return super().changelist_view(request, extra_context=extra_context)


# Register your models here.
