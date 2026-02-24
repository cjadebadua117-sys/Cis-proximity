from django.test import TestCase, Client
from django.contrib.auth.models import User


class RegistrationTests(TestCase):
    """Ensure student and instructor registration workflows function correctly."""

    def setUp(self):
        self.client = Client(HTTP_HOST='localhost')

    def test_unified_student_registration(self):
        response = self.client.post(
            '/register/',
            {
                'username': 'student_unified',
                'email': 'su@example.com',
                'password1': 'pass12345',
                'password2': 'pass12345',
                'user_type': 'student',
            },
        )
        # successful registration should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='student_unified').exists())

    def test_unified_instructor_registration(self):
        # need at least one section to assign
        from .models import Section
        Section.objects.create(year=1, section='A')
        response = self.client.post(
            '/register/',
            {
                'username': 'instr_unified',
                'email': 'iu@example.com',
                'password1': 'pass12345',
                'password2': 'pass12345',
                'user_type': 'instructor',
                'advisor_section': Section.objects.first().id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='instr_unified').exists())
        self.assertIsNotNone(User.objects.get(username='instr_unified').instructor_profile)

    def test_legacy_student_registration(self):
        # submit via ?type=student without including user_type field
        response = self.client.post(
            '/register/?type=student',
            {
                'username': 'legacy_student',
                'email': 'ls@example.com',
                'password1': 'pass12345',
                'password2': 'pass12345',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='legacy_student').exists())

    def test_missing_user_type_shows_error(self):
        # posting from legacy form but without query parameter should show form error
        response = self.client.post(
            '/register/',
            {
                'username': 'no_type',
                'email': 'nt@example.com',
                'password1': 'pass12345',
                'password2': 'pass12345',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required', status_code=200)

    def test_times_filter_returns_range(self):
        # verify that the custom times filter produces an iterable range
        from .templatetags.utils_tags import times
        self.assertEqual(list(times(0)), [])
        self.assertEqual(list(times(3)), [0, 1, 2])
        self.assertEqual(list(times('5')), [0, 1, 2, 3, 4])
        self.assertEqual(list(times('bad')), [])

    def test_instructor_dashboard_handles_empty_heatmap(self):
        # create an instructor user with profile but no students/sign-in
        from django.contrib.auth.models import User
        from .models import InstructorProfile
        instr = User.objects.create_user(username='instr_heat', password='pass')
        InstructorProfile.objects.create(user=instr, section=None)
        # log in and request dashboard
        self.client.login(username='instr_heat', password='pass')
        response = self.client.get('/instructor/dashboard/')
        self.assertEqual(response.status_code, 200)
        # page should load and heatmap_padding context variable should be 0
        self.assertIn('heatmap_padding', response.context)
        self.assertEqual(response.context['heatmap_padding'], 0)
