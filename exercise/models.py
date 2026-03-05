# exercise/models.py

from django.db import models
from django.contrib.auth import get_user_model
import os

User = get_user_model()

class ExerciseItem(models.Model):
    CATEGORY_CHOICES = [
        ('core_six_height_max_essentials', 'Core 6 - HeightMax Essentials'),
        ('core_four_height_max_posture', 'Core 4 - HeightMax Posture'),
        ('core_two_height_max_hgh', 'Core 2 - HeightMax HGH'),
        ('extras_to_pick', 'Extras To Pick From'),
        
    ]

    AGE_GROUP_CHOICES = [
        ('13-17', '13-17'),
        ('18-20', '18-20'),
        ('21-29', '21-29'),
        ('30-39', '30-39'),
        ('40-49', '40-49'),
        ('50-59', '50-59'),
        ('60+', '60+'),  # This is automatically assigned if the user is 21 or older
    ]

    title = models.CharField(max_length=255)
    points = models.IntegerField()
    serving_description = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES,default='height_max_essentials')
    age_group = models.CharField(max_length=5, choices=AGE_GROUP_CHOICES,default='13-17')
    image = models.ImageField(upload_to='exercise_items/')

    def __str__(self):
        return f"{self.title} ({self.category}, {self.age_group})"
    
    def save(self, *args, **kwargs):
        try:
            old_instance = ExerciseItem.objects.get(pk=self.pk)
            if old_instance.image and old_instance.image != self.image:
                # delete old image file
                if os.path.isfile(old_instance.image.path):
                    os.remove(old_instance.image.path)
        except ExerciseItem.DoesNotExist:
            pass  # object is new, so no old image

        super().save(*args, **kwargs)


class ExerciseSubmission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    Exercise_item = models.ForeignKey(ExerciseItem, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)  # NEW

    def __str__(self):
        return f"{self.user.username} - {self.Exercise_item.title} on {self.date}"
