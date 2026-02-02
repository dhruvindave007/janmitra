"""
Media Storage Serializers - For Encrypted Media Attachments
"""

from rest_framework import serializers

from .models import ReportMedia, MediaAccessLog


class ReportMediaUploadSerializer(serializers.ModelSerializer):
    """
    Serializer for uploading encrypted media.
    
    Media is encrypted client-side before upload.
    """
    
    class Meta:
        model = ReportMedia
        fields = [
            'id',
            'report',
            'encrypted_file',
            'encryption_key_encrypted',
            'mime_type',
            'file_size',
            'file_hash',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_file_size(self, value):
        """Ensure file size is within limits."""
        max_size = 50 * 1024 * 1024  # 50 MB
        if value and value > max_size:
            raise serializers.ValidationError(
                f"File size cannot exceed {max_size // (1024 * 1024)} MB."
            )
        return value
    
    def validate_mime_type(self, value):
        """Ensure only allowed mime types."""
        allowed_types = [
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/webp',
            'video/mp4',
            'video/webm',
            'audio/mpeg',
            'audio/wav',
            'audio/ogg',
            'application/pdf',
            'application/octet-stream',  # For encrypted files
        ]
        
        if value and value not in allowed_types:
            raise serializers.ValidationError(
                f"Mime type '{value}' is not allowed."
            )
        return value
    
    def create(self, validated_data):
        """Create media with the current user as uploader."""
        request = self.context.get('request')
        validated_data['uploaded_by'] = request.user
        return super().create(validated_data)


class ReportMediaListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing media attachments.
    """
    
    uploaded_by_email = serializers.CharField(
        source='uploaded_by.email', 
        read_only=True, 
        allow_null=True
    )
    
    class Meta:
        model = ReportMedia
        fields = [
            'id',
            'report',
            'mime_type',
            'file_size',
            'uploaded_by',
            'uploaded_by_email',
            'created_at',
        ]
        read_only_fields = fields


class ReportMediaDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for a single media attachment.
    
    Includes encryption key for authorized access.
    """
    
    uploaded_by_email = serializers.CharField(
        source='uploaded_by.email', 
        read_only=True, 
        allow_null=True
    )
    
    class Meta:
        model = ReportMedia
        fields = [
            'id',
            'report',
            'encrypted_file',
            'encryption_key_encrypted',
            'mime_type',
            'file_size',
            'file_hash',
            'uploaded_by',
            'uploaded_by_email',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class MediaAccessLogSerializer(serializers.ModelSerializer):
    """
    Serializer for media access logs.
    
    Read-only - used for audit purposes.
    """
    
    accessed_by_email = serializers.CharField(
        source='accessed_by.email', 
        read_only=True, 
        allow_null=True
    )
    
    class Meta:
        model = MediaAccessLog
        fields = [
            'id',
            'media',
            'accessed_by',
            'accessed_by_email',
            'access_type',
            'ip_address',
            'device_fingerprint',
            'created_at',
        ]
        read_only_fields = fields
