from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    telegram_id = models.BigIntegerField(unique=True, db_index=True, default=0)
    is_anonymous_mode = models.BooleanField(default=True)
    total_confessions = models.IntegerField(default=0)
    total_comments = models.IntegerField(default=0)
    impact_points = models.IntegerField(default=0)
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['telegram_id']),
        ]


class Confession(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='confessions')
    text = models.TextField(max_length=4096)
    is_anonymous = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    channel_message_id = models.BigIntegerField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_confessions')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']


class Comment(models.Model):
    confession = models.ForeignKey(Confession, on_delete=models.CASCADE, related_name='comments', db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    parent_comment = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    text = models.TextField(max_length=1000)
    like_count = models.IntegerField(default=0)
    dislike_count = models.IntegerField(default=0)
    report_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['confession']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']


class Reaction(models.Model):
    REACTION_CHOICES = [
        ('like', 'Like'),
        ('dislike', 'Dislike'),
        ('report', 'Report'),
    ]
    
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reactions')
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('comment', 'user')
        indexes = [
            models.Index(fields=['comment', 'user']),
        ]
