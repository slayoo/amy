import re
import yaml
import csv
import requests

from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic.edit import CreateView, UpdateView

from workshops.models import Site, Airport, Event, Person, Task, Cohort, Skill, Trainee, Badge, Award, Role
from workshops.forms import SearchForm, InstructorsForm, PersonBulkAddForm
from workshops.util import earth_distance

from workshops.models import \
    Airport, \
    Award, \
    Badge, \
    Cohort, \
    Event, \
    Person, \
    Site, \
    Skill, \
    Task, \
    Trainee

#------------------------------------------------------------

ITEMS_PER_PAGE = 25

#------------------------------------------------------------

def index(request):
    '''Home page.'''
    upcoming_events = Event.objects.upcoming_events()
    unpublished_events = Event.objects.unpublished_events()
    context = {'title' : None,
               'upcoming_events' : upcoming_events,
               'unpublished_events' : unpublished_events}
    return render(request, 'workshops/index.html', context)

#------------------------------------------------------------

SITE_FIELDS = ['domain', 'fullname', 'country', 'notes']


def all_sites(request):
    '''List all sites.'''

    all_sites = Site.objects.order_by('domain')
    sites = _get_pagination_items(request, all_sites)
    user_can_add = request.user.has_perm('edit')
    context = {'title' : 'All Sites',
               'all_sites' : sites,
               'user_can_add' : user_can_add}
    return render(request, 'workshops/all_sites.html', context)


def site_details(request, site_domain):
    '''List details of a particular site.'''
    site = Site.objects.get(domain=site_domain)
    events = Event.objects.filter(site=site)
    context = {'title' : 'Site {0}'.format(site),
               'site' : site,
               'events' : events}
    return render(request, 'workshops/site.html', context)


class SiteCreate(CreateView):
    model = Site
    fields = SITE_FIELDS


class SiteUpdate(UpdateView):
    model = Site
    fields = SITE_FIELDS
    slug_field = 'domain'
    slug_url_kwarg = 'site_domain'

#------------------------------------------------------------

AIRPORT_FIELDS = ['iata', 'fullname', 'country', 'latitude', 'longitude']


def all_airports(request):
    '''List all airports.'''
    all_airports = Airport.objects.order_by('iata')
    user_can_add = request.user.has_perm('edit')
    context = {'title' : 'All Airports',
               'all_airports' : all_airports,
               'user_can_add' : user_can_add}
    return render(request, 'workshops/all_airports.html', context)


def airport_details(request, airport_iata):
    '''List details of a particular airport.'''
    airport = Airport.objects.get(iata=airport_iata)
    context = {'title' : 'Airport {0}'.format(airport),
               'airport' : airport}
    return render(request, 'workshops/airport.html', context)


class AirportCreate(CreateView):
    model = Airport
    fields = AIRPORT_FIELDS


class AirportUpdate(UpdateView):
    model = Airport
    fields = AIRPORT_FIELDS
    slug_field = 'iata'
    slug_url_kwarg = 'airport_iata'

#------------------------------------------------------------

PERSON_UPLOAD_FIELDS = ['personal', 'middle', 'family', 'email']
PERSON_TASK_UPLOAD_FIELDS = PERSON_UPLOAD_FIELDS + ['event', 'role']

def all_persons(request):
    '''List all persons.'''

    all_persons = Person.objects.order_by('family', 'personal')
    persons = _get_pagination_items(request, all_persons)
    context = {'title' : 'All Persons',
               'all_persons' : persons}
    return render(request, 'workshops/all_persons.html', context)


def person_details(request, person_id):
    '''List details of a particular person.'''
    person = Person.objects.get(id=person_id)
    awards = Award.objects.filter(person__id=person_id)
    tasks = Task.objects.filter(person__id=person_id)
    context = {'title' : 'Person {0}'.format(person),
               'person' : person,
               'awards' : awards,
               'tasks' : tasks}
    return render(request, 'workshops/person.html', context)


def person_bulk_add(request):
    if request.method == 'POST':
        form = PersonBulkAddForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                persons_tasks = _upload_person_task_csv(request,
                                                        request.FILES['file'])
            except csv.Error as e:
                messages.add_message(request, messages.ERROR,
                                     "Error processing uploaded .CSV file: {}"
                                     .format(e))
            else:
                # instead of insta-saving, put everything into session
                # then redirect to confirmation page which in turn saves the
                # data

                request.session['bulk-add-people'] = persons_tasks

                return redirect('person_bulk_add_confirmation')

    else:
        form = PersonBulkAddForm()

    context = {'title': 'Bulk Add People',
               'form': form}
    return render(request, 'workshops/person_bulk_add_form.html', context)


def person_bulk_add_confirmation(request):
    persons_tasks = request.session['bulk-add-people']

    # if the session is empty, don't bother
    if not persons_tasks:
        raise Http404

    if request.method == 'POST':
        # check if user wants to verify or save, or cancel

        if request.POST.get('verify', None):
            # if there's "verify" in POST, then do only verification
            any_errors = _verify_upload_person_task(persons_tasks)
            if any_errors:
                messages.add_message(request, messages.ERROR,
                                     "Please make sure to fix all errors "
                                     "listed below.")

            context = {'title': 'Confirm uploaded data',
                       'persons_tasks': persons_tasks}
            return render(request, 'workshops/person_bulk_add_results.html',
                          context)

        elif (request.POST.get('confirm', None) and
                not request.POST.get('cancel', None)):
            # there must be "confirm" and no "cancel" in POST in order to save

            # TODO: update values if user wants to change them
            _verify_upload_person_task(persons_tasks)

            try:
                records = 0
                with transaction.atomic():
                    for row in persons_tasks:
                        # create person
                        p = Person(**row['person'])
                        p.save()
                        records += 1

                        # create task if data supplied
                        if row['event'] and row['role']:
                            e = Event.objects.get(slug=row['event'])
                            r = Role.objects.get(name=row['role'])
                            t = Task(person=p, event=e, role=r)
                            t.save()
                            records += 1

            except (IntegrityError, ObjectDoesNotExist) as e:
                messages.add_message(request, messages.ERROR,
                                     "Error saving data to the database: {}. "
                                     "Please make sure to fix all errors "
                                     "listed below.".format(e))
                context = {'title': 'Confirm uploaded data',
                           'persons_tasks': persons_tasks}
                return render(request,
                              'workshops/person_bulk_add_results.html',
                              context)

            else:
                request.session['bulk-add-people'] = None
                messages.add_message(request, messages.SUCCESS,
                                     "Successfully bulk-loaded {} records."
                                     .format(records))
                return redirect('person_bulk_add')

        else:
            # any "cancel" or no "confirm" in POST cancels the upload
            request.session['bulk-add-people'] = None
            return redirect('person_bulk_add')

    else:
        # alters persons_tasks via reference
        _verify_upload_person_task(persons_tasks)

        context = {'title': 'Confirm uploaded data',
                   'persons_tasks': persons_tasks}
        return render(request, 'workshops/person_bulk_add_results.html',
                      context)


def _upload_person_task_csv(request, uploaded_file):
    """
    Read data from CSV and turn it into JSON-serializable list of dictionaries.
    "Serializability" is required because we put this data into session.  See
    https://docs.djangoproject.com/en/1.7/topics/http/sessions/ for details.
    """
    persons_tasks = []
    reader = csv.DictReader(uploaded_file)
    for row in reader:
        person_fields = dict((col, row[col].strip())
                             for col in PERSON_UPLOAD_FIELDS)
        entry = {'person': person_fields, 'event': row.get('event', None),
                 'role': row.get('role', None), 'errors': None}
        persons_tasks.append(entry)
    return persons_tasks


def _verify_upload_person_task(data):
    """
    Verify that uploaded data is correct.  Show errors by populating ``errors``
    dictionary item.

    This function changes ``data`` in place; ``data`` is a list, so it's
    passed by a reference.  This means any changes to ``data`` we make in
    here don't need to be returned via ``return`` statement.
    """

    errors_occur = False

    for item in data:
        event, role = item.get('event', None), item.get('role', None)
        email = item['person'].get('email', None)

        errors = []
        if event:
            try:
                Event.objects.get(slug=event)
            except Event.DoesNotExist:
                errors.append('Event with slug {} does not exist.'
                              .format(event))
        if role:
            try:
                Role.objects.get(name=role)
            except Role.DoesNotExist:
                errors.append('Role with name {} does not exist.'.format(role))
            except Role.MultipleObjectsReturned:
                errors.append('More than one role named {} exists.'
                              .format(role))

        if email:
            try:
                Person.objects.get(email=email)
                errors.append("User with email {} already exists."
                              .format(email))
            except Person.DoesNotExist:
                # we want the email to be unique
                pass

        if errors:
            # copy the errors just to be safe
            item['errors'] = errors[:]
            if not errors_occur:
                errors_occur = True

    # indicate there were some errors
    return errors_occur


class PersonCreate(CreateView):
    model = Person
    fields = '__all__'


class PersonUpdate(UpdateView):
    model = Person
    fields = '__all__'
    pk_url_kwarg = 'person_id'


#------------------------------------------------------------

def all_events(request):
    '''List all events.'''

    all_events = Event.objects.order_by('id')
    events = _get_pagination_items(request, all_events)
    for e in events:
        e.num_instructors = e.task_set.filter(role__name='instructor').count()
    context = {'title' : 'All Events',
               'all_events' : events}
    return render(request, 'workshops/all_events.html', context)


def event_details(request, event_ident):
    '''List details of a particular event.'''

    event = Event.get_by_ident(event_ident)
    tasks = Task.objects.filter(event__id=event.id).order_by('role__name')
    context = {'title' : 'Event {0}'.format(event),
               'event' : event,
               'tasks' : tasks}
    return render(request, 'workshops/event.html', context)

def validate_event(request, event_ident):
    '''Check the event's home page *or* the specified URL (for testing).'''
    page_url, error_messages = None, []
    event = Event.get_by_ident(event_ident)
    github_url = request.GET.get('url', None) # for manual override
    if github_url is None:
        github_url = event.url
    if github_url is not None:
        page_url = github_url.replace('github.com', 'raw.githubusercontent.com').rstrip('/') + '/gh-pages/index.html'
        response = requests.get(page_url)
        if response.status_code != 200:
            error_messages.append('Request for {0} returned status code {1}'.format(page_url, response.status_code))
        else:
            valid, error_messages = check_file(page_url, response.text)
    context = {'title' : 'Validate Event {0}'.format(event),
               'event' : event,
               'page' : page_url,
               'error_messages' : error_messages}
    return render(request, 'workshops/validate_event.html', context)


class EventCreate(CreateView):
    model = Event
    fields = '__all__'


class EventUpdate(UpdateView):
    model = Event
    fields = '__all__'
    pk_url_kwarg = 'event_ident'

#------------------------------------------------------------

TASK_FIELDS = ['event', 'person', 'role']


def all_tasks(request):
    '''List all tasks.'''

    all_tasks = Task.objects.order_by('event', 'person', 'role')
    tasks = _get_pagination_items(request, all_tasks)
    user_can_add = request.user.has_perm('edit')
    context = {'title' : 'All Tasks',
               'all_tasks' : tasks,
               'user_can_add' : user_can_add}
    return render(request, 'workshops/all_tasks.html', context)


def task_details(request, event_slug, person_id, role_name):
    '''List details of a particular task.'''
    task = Task.objects.get(event__slug=event_slug, person__id=person_id, role__name=role_name)
    context = {'title' : 'Task {0}'.format(task),
               'task' : task}
    return render(request, 'workshops/task.html', context)


class TaskCreate(CreateView):
    model = Task
    fields = TASK_FIELDS


class TaskUpdate(UpdateView):
    model = Task
    fields = TASK_FIELDS
    pk_url_kwarg = 'task_id'

    def get_object(self):
        """
        Returns the object the view is displaying.
        """

        event_slug = self.kwargs.get('event_slug', None)
        person_id = self.kwargs.get('person_id', None)
        role_name = self.kwargs.get('role_name', None)

        return get_object_or_404(Task, event__slug=event_slug, person__id=person_id, role__name=role_name)

#------------------------------------------------------------

COHORT_FIELDS = ['name', 'start', 'active', 'venue', 'qualifies']


def all_cohorts(request):
    '''List all cohorts.'''
    all_cohorts = Cohort.objects.order_by('start')
    user_can_add = request.user.has_perm('edit')
    context = {'title' : 'All Cohorts',
               'all_cohorts' : all_cohorts,
               'user_can_add' : user_can_add}
    return render(request, 'workshops/all_cohorts.html', context)


def cohort_details(request, cohort_name):
    '''List details of a particular cohort.'''
    cohort = Cohort.objects.get(name=cohort_name)
    trainees = Trainee.objects.filter(cohort_id=cohort.id)
    context = {'title' : 'Cohort {0}'.format(cohort),
               'cohort' : cohort,
               'trainees' : trainees}
    return render(request, 'workshops/cohort.html', context)


class CohortCreate(CreateView):
    model = Cohort
    fields = COHORT_FIELDS


class CohortUpdate(UpdateView):
    model = Cohort
    fields = COHORT_FIELDS
    slug_field = 'name'
    slug_url_kwarg = 'cohort_name'

#------------------------------------------------------------

def all_badges(request):
    '''List all badges.'''

    all_badges = Badge.objects.order_by('name')
    for b in all_badges:
        b.num_awarded = Award.objects.filter(badge_id=b.id).count()
    context = {'title' : 'All Badges',
               'all_badges' : all_badges}
    return render(request, 'workshops/all_badges.html', context)


def badge_details(request, badge_name):
    '''Show who has a particular badge.'''

    badge = Badge.objects.get(name=badge_name)
    all_awards = Award.objects.filter(badge_id=badge.id)
    awards = _get_pagination_items(request, all_awards)
    context = {'title' : 'Badge {0}'.format(badge.title),
               'badge' : badge,
               'all_awards' : awards}
    return render(request, 'workshops/badge.html', context)

#------------------------------------------------------------

def instructors(request):
    '''Search for instructors.'''

    persons = None

    if request.method == 'POST':
        form = InstructorsForm(request.POST)
        if form.is_valid():

            # Filter by skills.
            persons = Person.objects.filter(airport__isnull=False)
            skills = []
            for s in Skill.objects.all():
                if form.cleaned_data[s.name]:
                    skills.append(s)
            persons = persons.have_skills(skills)

            # Add metadata which we will eventually filter by
            for person in persons:
                person.num_taught = \
                    person.task_set.filter(role__name='instructor').count()

            # Sort by location.
            loc = (form.cleaned_data['latitude'],
                   form.cleaned_data['longitude'])
            persons = [(earth_distance(loc, (p.airport.latitude, p.airport.longitude)), p)
                       for p in persons]
            persons.sort(
                key=lambda distance_person: (
                    distance_person[0],
                    distance_person[1].family,
                    distance_person[1].personal,
                    distance_person[1].middle))
            persons = [x[1] for x in persons[:10]]

    # if a GET (or any other method) we'll create a blank form
    else:
        form = InstructorsForm()

    context = {'title' : 'Find Instructors',
               'form': form,
               'persons' : persons}
    return render(request, 'workshops/instructors.html', context)

#------------------------------------------------------------

def search(request):
    '''Search the database by term.'''

    term, sites, events, persons = '', None, None, None

    if request.method == 'POST':
        form = SearchForm(request.POST)
        if form.is_valid():
            term = form.cleaned_data['term']
            if form.cleaned_data['in_sites']:
                sites = Site.objects.filter(
                    Q(domain__contains=term) |
                    Q(fullname__contains=term) |
                    Q(notes__contains=term))
            if form.cleaned_data['in_events']:
                events = Event.objects.filter(
                    Q(slug__contains=term) |
                    Q(notes__contains=term))
            if form.cleaned_data['in_persons']:
                persons = Person.objects.filter(
                    Q(personal__contains=term) |
                    Q(family__contains=term) |
                    Q(email__contains=term) |
                    Q(github__contains=term))
        else:
            pass # FIXME: error message

    # if a GET (or any other method) we'll create a blank form
    else:
        form = SearchForm()

    context = {'title' : 'Search',
               'form': form,
               'term' : term,
               'sites' : sites,
               'events' : events,
               'persons' : persons}
    return render(request, 'workshops/search.html', context)

#------------------------------------------------------------

def _export_badges():
    '''Collect badge data as YAML.'''
    result = {}
    for badge in Badge.objects.all():
        persons = Person.objects.filter(award__badge_id=badge.id)
        result[badge.name] = [{"user" : p.slug, "name" : p.fullname()} for p in persons]
    return result


def _export_instructors():
    '''Collect instructor airport locations as YAML.'''
    # Exclude airports with no instructors, and add the number of instructors per airport
    airports = Airport.objects.exclude(person=None).annotate(num_persons=Count('person'))
    return [{'airport' : str(a.fullname),
             'latlng' : '{0},{1}'.format(a.latitude, a.longitude),
             'count'  : a.num_persons}
            for a in airports]


def export(request, name):
    '''Export data as YAML for inclusion in main web site.'''
    data = None
    if name == 'badges':
        title, data = 'Badges', _export_badges()
    elif name == 'instructors':
        title, data = 'Instructor Locations', _export_instructors()
    else:
        title, data = 'Error', None # FIXME - need an error message
    context = {'title' : title,
               'data' : data}
    return render(request, 'workshops/export.html', context)

#------------------------------------------------------------

def _get_pagination_items(request, all_objects):
    '''Select paginated items.'''

    # Get parameters.
    items = request.GET.get('items_per_page', ITEMS_PER_PAGE)
    if items != 'all':
        try:
            items = int(items)
        except ValueError:
            items = ITEMS_PER_PAGE

    # Figure out where we are.
    page = request.GET.get('page')

    # Show everything.
    if items == 'all':
        result = all_objects

    # Show selected items.
    else:
        paginator = Paginator(all_objects, items)

        # Select the sites.
        try:
            result = paginator.page(page)

        # If page is not an integer, deliver first page.
        except PageNotAnInteger:
            result = paginator.page(1)

        # If page is out of range, deliver last page of results.
        except EmptyPage:
            result = paginator.page(paginator.num_pages)

    return result
