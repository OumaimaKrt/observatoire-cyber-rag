# backend/api/models.py
from django.db import models

class CyberIncident(models.Model):
    titre = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    type_menace = models.CharField(max_length=100, blank=True, null=True)
    secteur_cible = models.CharField(max_length=100, blank=True, null=True)
    severite = models.CharField(max_length=50, blank=True, null=True)
    source = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cyber_incidents'  # ⬅️ Ta table existante
        ordering = ['-created_at']
        managed = False  # ⬅️ IMPORTANT : Ne pas créer la table

    def __str__(self):
        return self.titre[:100]