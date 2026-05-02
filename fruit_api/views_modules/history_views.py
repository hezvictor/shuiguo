from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from fruit_api.serializers import DetectionHistoryListSerializer, DetectionHistorySerializer
from fruit_api.services.auth.history_service import delete_history_with_report, history_queryset_for_user


class DetectionHistoryPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class DetectionHistoryListView(generics.ListAPIView):
    """List current user detection history; supports optional detection_type filter."""

    serializer_class = DetectionHistoryListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DetectionHistoryPagination

    def get_queryset(self):
        detection_type = self.request.query_params.get('detection_type')
        return history_queryset_for_user(self.request.user, detection_type=detection_type)


class DetectionHistoryDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve/Delete one history record for current user."""

    serializer_class = DetectionHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return history_queryset_for_user(self.request.user)

    def perform_destroy(self, instance):
        delete_history_with_report(instance)

