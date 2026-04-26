from django.db import models

# Create your models here.


class LogBlock(models.Model):
    user = models.IntegerField(null=True, blank=True)  # Updated to expect an integer
    group = models.CharField(max_length=255)
    time_block = models.CharField(max_length=16)
    # statistics about the events, e.g., counts, durations, etc.
    statistics = models.JSONField(default=dict)  # Added default value for statistics
    # log data, a list of JSON objects representing the events
    log_data = models.JSONField(default=list)

    def __str__(self):
        return f"{self.group} - {self.time_block}"

    # Removed the s3_path field and added a method to generate it dynamically
    def get_s3_path(self):
        return (
            f"event_logs/{self.group}/{self.time_block[:8]}/{self.time_block[8:]}.json"
        )
