import os
import sys
from datetime import timedelta
from collections import defaultdict

# Ensure project root is on sys.path so Django settings module can be imported
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swrs_config.settings')
import django
django.setup()

from presence_app.models import LaboratoryHistory, LegacyLaboratoryHistory, SignInRecord
from django.db.utils import OperationalError
from pytz import timezone as tz

lab_rows = []
total = 0

try:
    qs = LaboratoryHistory.objects.select_related('student', 'room').all().order_by('-exit_time')
    for r in qs:
        entrance_time = r.exit_time - timedelta(minutes=r.duration_minutes) if r.duration_minutes else r.exit_time
        lab_rows.append({'entrance_time': entrance_time, 'exit_time': r.exit_time})
    total = qs.count()
except OperationalError:
    legacy_qs = LegacyLaboratoryHistory.objects.all().order_by('-entry_time')
    for r in legacy_qs:
        entrance_time = None
        try:
            possible = SignInRecord.objects.filter(student_id=r.student_id, sign_out_time__isnull=False).order_by('-sign_out_time')
            if possible.exists():
                candidate = possible.first()
                time_diff = abs((candidate.sign_out_time - r.entry_time).total_seconds())
                if time_diff <= 300:
                    entrance_time = candidate.sign_in_time
        except Exception:
            pass
        lab_rows.append({'entrance_time': entrance_time, 'exit_time': r.entry_time})
    total = legacy_qs.count()

# Group by date (Asia/Manila)
philippines_tz = tz('Asia/Manila')
groups = defaultdict(int)
for rec in lab_rows:
    dt = rec.get('entrance_time') or rec.get('exit_time')
    if not dt:
        continue
    try:
        date_key = dt.astimezone(philippines_tz).date() if hasattr(dt, 'astimezone') else dt.date()
    except Exception:
        date_key = dt.date()
    groups[date_key] += 1

print('TOTAL_RECORDS:', total)
for day in sorted(groups.keys(), reverse=True):
    print(day.strftime('%Y-%m-%d'), groups[day])

# Exit cleanly
sys.exit(0)
