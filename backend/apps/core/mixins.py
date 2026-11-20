from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response


class SoftDeleteViewSetMixin:
    """DELETE marks is_deleted=True (row stays for history). POST {id}/restore/ brings it back."""

    def perform_destroy(self, instance):
        instance.soft_delete(self.request.user)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        model = self.get_serializer_class().Meta.model
        instance = get_object_or_404(model.all_objects, pk=pk, is_deleted=True)
        self.check_object_permissions(request, instance)
        instance.restore()
        return Response(self.get_serializer(instance).data, status=status.HTTP_200_OK)
