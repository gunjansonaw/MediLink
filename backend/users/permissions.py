from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins to edit it.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        return obj == request.user


class IsDoctorOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow doctors or admins.
    """
    def has_permission(self, request, view):
        return request.user.role in ['doctor', 'admin']


class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admins.
    """
    def has_permission(self, request, view):
        return request.user.role == 'admin'


class IsPatient(permissions.BasePermission):
    """
    Custom permission to only allow patients.
    """
    def has_permission(self, request, view):
        return request.user.role == 'patient'
