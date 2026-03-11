from logging import getLogger

from django.db import transaction
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models import Contract
from conpass.models.constants import ContractTypeable
from conpass.services.directory.directory_service import DirectoryService
from conpass.views.contract.serializer.contract_related_serializer import ContractBriefInfoSerializer

logger = getLogger(__name__)


class ContractRelationsView(APIView):
    """
    GET /contract/<contract_id>/relations/
    親子関係と関係書類をまとめて返す

    Response:
    {
        "parent":      <ContractBriefInfo | null>,
        "children":    [<ContractBriefInfo>, ...],
        "related_docs":[<ContractBriefInfo>, ...],
    }
    """

    def _allowed_ids(self, user):
        directories = DirectoryService().get_allowed_directories(
            user, ContractTypeable.ContractType.CONTRACT.value
        )
        return [d.id for d in directories]

    def get(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)
        allowed = self._allowed_ids(request.user)

        # 親
        parent_data = None
        if contract.related_parent_id:
            parent = contract.related_parent
            if parent and not parent.is_garbage and parent.directory_id in allowed:
                parent_data = ContractBriefInfoSerializer(parent).data

        # 子
        children_qs = (
            contract.children
            .filter(directory__id__in=allowed, is_garbage=False)
            .prefetch_related('meta_data_contract')
        )
        children_data = ContractBriefInfoSerializer(children_qs, many=True).data

        # 関係書類
        related_qs = (
            contract.related_contracts
            .filter(directory__id__in=allowed, is_garbage=False)
            .prefetch_related('meta_data_contract')
        )
        related_data = ContractBriefInfoSerializer(related_qs, many=True).data

        return Response({
            'parent': parent_data,
            'children': children_data,
            'related_docs': related_data,
        })


class ContractParentView(APIView):
    """
    親子関係の設定・解除

    POST /contract/<contract_id>/parent/
        body: {"parent_id": <int>}
        → related_parent を設定し is_child_contract=True にする

    DELETE /contract/<contract_id>/parent/
        → related_parent を解除し is_child_contract=False にする
    """

    @transaction.atomic
    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)
        parent_id = request.data.get('parent_id')
        if not parent_id:
            return Response({'error': 'parent_id は必須です'}, status=status.HTTP_400_BAD_REQUEST)

        if int(parent_id) == contract_id:
            return Response({'error': '自分自身を親に設定できません'}, status=status.HTTP_400_BAD_REQUEST)

        parent = get_object_or_404(Contract, id=parent_id, account=request.user.account)
        contract.related_parent = parent
        contract.is_child_contract = True
        contract.save(update_fields=['related_parent', 'is_child_contract'])

        return Response(ContractBriefInfoSerializer(parent).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def delete(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)
        contract.related_parent = None
        contract.is_child_contract = False
        contract.save(update_fields=['related_parent', 'is_child_contract'])

        return Response(status=status.HTTP_204_NO_CONTENT)
