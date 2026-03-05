# wellness/models.py

from django.db import models
from django.contrib.auth import get_user_model
import os

User = get_user_model()

class WellnessItem(models.Model):
    CATEGORY_CHOICES = [
        ('spine_support', 'Spine Support & Disc Lubrication Foods'),
        ('posture_muscle', 'Posture Muscle Repair & Fuel Foods'),
        ('growth_boost', 'Growth Boosting Foods'),
        ('sleep', 'Sleep'),
        ('sunlight', 'Sunlight'),
        ('meditation', 'Meditation'),
        ('hydration', 'Hydration'),
    ]

    AGE_GROUP_CHOICES = [
        ('13-17', '13-17'),
        ('13-20', '13-20'),
        ('18-20', '18-20'),
        ('21+', '21+'),  # This is automatically assigned if the user is 21 or older
    ]

    title = models.CharField(max_length=255)
    points = models.IntegerField()
    serving_description = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES,default='spine_support')
    age_group = models.CharField(max_length=5, choices=AGE_GROUP_CHOICES,default='21+')
    image = models.ImageField(upload_to='wellness_items/')

    def __str__(self):
        return f"{self.title} ({self.category}, {self.age_group})"
    
    def save(self, *args, **kwargs):
        try:
            old_instance = WellnessItem.objects.get(pk=self.pk)
            if old_instance.image and old_instance.image != self.image:
                # delete old image file
                if os.path.isfile(old_instance.image.path):
                    os.remove(old_instance.image.path)
        except WellnessItem.DoesNotExist:
            pass  # object is new, so no old image

        super().save(*args, **kwargs)


class WellnessSubmission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    wellness_item = models.ForeignKey(WellnessItem, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)  # NEW

    def __str__(self):
        return f"{self.user.username} - {self.wellness_item.title} on {self.date}"
