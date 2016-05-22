from django.core.urlresolvers import reverse

from .base import TestBase
from ..models import Person, Role, TrainingRequest


class TestSWCEventRequestForm(TestBase):
    def setUp(self):
        self._setUpUsersAndLogin()
        self._setUpRoles()

    def test_request_added(self):
        data = {
            'personal': 'John',
            'family': 'Smith',
            'email': 'john@smith.com',
            'occupation': '',
            'occupation_other': 'unemployed',
            'affiliation': 'AGH University of Science and Technology',
            'location': 'Cracow',
            'country': 'PL',
            'domains': [1, 2],
            'domains_other': '',
            'gender': Person.MALE,
            'gender_other': '',
            'previous_involvement': [Role.objects.get(name='host').id],
            'previous_training': 'none',
            'previous_training_other': '',
            'previous_experience': 'none',
            'previous_experience_other': '',
            'programming_language_usage_frequency': 'hourly',
            'reason': 'Just for fun.',
            'teaching_frequency_expectation': 'often',
            'teaching_frequency_expectation_other': '',
            'max_travelling_frequency': 'yearly',
            'max_travelling_frequency_other': '',
            'addition_skills': '',
            'agreed_to_code_of_conduct': 'on',
            'agreed_to_complete_training': 'on',
            'agreed_to_teach_workshops': 'on',
            'recaptcha_response_field': 'PASSED',
        }
        rv = self.client.post(reverse('training_request'), data,
                              follow=True)
        self.assertEqual(rv.status_code, 200)
        content = rv.content.decode('utf-8')
        self.assertNotIn('Fix errors below', content)
        self.assertEqual(TrainingRequest.objects.all().count(), 1)
