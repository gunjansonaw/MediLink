from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins to edit it.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(request.user, 'role', None) == 'admin':
            return True
        return obj == request.user


class IsDoctorOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow doctors or admins.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) in ['doctor', 'admin']
        )


class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admins.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) == 'admin'
        )


class IsPatient(permissions.BasePermission):
    """
    Custom permission to only allow patients.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) == 'patient'
        )
