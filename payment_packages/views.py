from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import PaymentPackage
from .serializers import PaymentPackageSerializer
from django.utils import timezone
from users.serializers import UserSerializer 


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_payment_packages(request):
    user = request.user
    print(UserSerializer(user).data)
    try:
        packages = PaymentPackage.objects.filter(deleted_at__isnull=True, is_free=False).order_by('-created_at')
        serialized = PaymentPackageSerializer(packages, many=True, context={'request': request})
        return Response({'message': 'Packages fetched successfully', 'data': serialized.data,'user':UserSerializer(user).data})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_package(request, package_id):
    try:
        package = PaymentPackage.objects.get(
            id=package_id,
            deleted_at__isnull=True
        )

        serialized = PaymentPackageSerializer(
            package,
            context={'request': request}  # ✅ REQUIRED
        )

        return Response({
            'message': 'Package fetched successfully',
            'data': serialized.data
        })

    except PaymentPackage.DoesNotExist:
        return Response(
            {'error': 'Package not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment_package(request):
    try:
        serializer = PaymentPackageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Package created successfully', 'data': serializer.data})
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_payment_package(request, package_id):
    try:
        package = PaymentPackage.objects.get(id=package_id, deleted_at__isnull=True)
        serializer = PaymentPackageSerializer(package, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Package updated successfully', 'data': serializer.data})
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except PaymentPackage.DoesNotExist:
        return Response({'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_payment_package(request, package_id):
    try:
        package = PaymentPackage.objects.get(id=package_id, deleted_at__isnull=True)
        package.deleted_at = timezone.now()
        package.save()
        return Response({'message': 'Package deleted (soft) successfully'})
    except PaymentPackage.DoesNotExist:
        return Response({'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
