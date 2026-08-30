# backend/api/serializers.py
from rest_framework import serializers
from .models import CyberIncident

class CyberIncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CyberIncident
        fields = [
            'id', 'titre', 'description', 'type_menace',
            'secteur_cible', 'severite', 'source', 'created_at'
        ]