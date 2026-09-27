from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import PasswordResetToken


class LoginTests(TestCase):
    def test_unknown_email_gets_generic_error(self):
        response = self.client.post(reverse('login'), {'email': 'nobody@example.com', 'password': 'x'}, follow=True)
        self.assertContains(response, 'Invalid email or password.')
        self.assertNotContains(response, 'does not exist')

    def test_duplicate_emails_do_not_crash(self):
        User.objects.create_user('a', 'dup@example.com', 'Str0ng-pass-1')
        User.objects.create_user('b', 'dup@example.com', 'Str0ng-pass-2')
        response = self.client.post(reverse('login'), {'email': 'dup@example.com', 'password': 'Str0ng-pass-2'})
        self.assertRedirects(response, reverse('user'))

    def test_logout_requires_post(self):
        User.objects.create_user('a', 'a@example.com', 'Str0ng-pass-1')
        self.client.login(username='a', password='Str0ng-pass-1')
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)


class SignupTests(TestCase):
    def test_allauth_signup_redirects_to_verified_signup(self):
        response = self.client.get('/accounts/signup/')
        self.assertRedirects(response, reverse('signup'), fetch_redirect_response=False)

    def test_unverified_account_does_not_block_real_owner(self):
        User.objects.create_user('squatter', 'owner@example.com', 'Str0ng-pass-1', is_active=False)
        self.client.post(reverse('signup'), {
            'username': 'owner', 'email': 'owner@example.com',
            'password1': 'An0ther-strong-pass', 'password2': 'An0ther-strong-pass',
        })
        self.assertFalse(User.objects.filter(username='squatter').exists())
        self.assertTrue(User.objects.filter(username='owner', email='owner@example.com').exists())


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('a', 'a@example.com', 'Str0ng-pass-1')
        self.token = PasswordResetToken.objects.create(user=self.user)
        self.url = reverse('reset_password', args=[str(self.token.token)])

    def test_empty_password_rejected(self):
        self.client.post(self.url, {'password': '', 'confirm_password': ''})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Str0ng-pass-1'))

    def test_weak_password_rejected(self):
        self.client.post(self.url, {'password': '123', 'confirm_password': '123'})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Str0ng-pass-1'))

    def test_strong_password_accepted(self):
        self.client.post(self.url, {'password': 'N3w-strong-pass!', 'confirm_password': 'N3w-strong-pass!'})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('N3w-strong-pass!'))
        self.assertFalse(PasswordResetToken.objects.exists())
