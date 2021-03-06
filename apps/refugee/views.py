import os
from formtools.wizard.views import SessionWizardView
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django_countries import countries

from userena.forms import SignupForm
from userena.models import UserenaSignup
from userena import signals as userena_signals
from common.forms import UserenaEditProfileForm
from .forms import *
from .models import Refugee, FamilyMember
from citizen_refuge.models import Application
from django.views.generic import ListView, TemplateView
from django.views.generic.edit import ProcessFormView
from common.helpers import GENDER, APPLICATION_STATUS
from django.core.exceptions import PermissionDenied

KEYS = ['userena', 'basic', 'family', 'address', 'country']
FORMS = [SignupForm, RefugeeSignUpBasic, FamilyMemberFormset, RefugeeSignUpAddress, RefugeeSignUpPreferences]
FORM_LIST = zip(KEYS, FORMS)
TEMPLATES = dict(zip(KEYS, ['refugee/' + k + '.html' for k in KEYS]))

def skip_family(wizard):
    """Return true if user opts to pay by credit card"""
    cleaned_data = wizard.storage.get_step_data('basic') or {'skip_family': '0'}
    return cleaned_data.get('skip_family', '0') != '1'

class RefugeeSignupWizard(SessionWizardView):
    form_list = FORM_LIST
    file_storage = FileSystemStorage(location='/tmp/')

    instance_dict = {
        'family': FamilyMember.objects.none()
    }

    condition_dict = {
        'family': skip_family
    }

    def __init__(self, *args, **kwargs):
        super(RefugeeSignupWizard, self).__init__(*args, **kwargs)

    def done(self, form_list, form_dict, **kwargs):
        # Create the user
        user = form_dict['userena'].save()
        mugshot = form_dict['basic'].cleaned_data.get('mugshot')
        user.my_profile.mugshot = mugshot
        user.my_profile.type = 'R'
        user.my_profile.save()

        # Set first and last name on user
        basic = form_dict['basic']
        user.first_name = basic.cleaned_data.get('first_name')
        user.last_name = basic.cleaned_data.get('last_name')
        user.save()

        # Concatenate all the information from the forms and save.
        refugee = Refugee(user=user)
        family_members = []
        for key in form_dict:
            if key == 'userena': continue
            form = form_dict[key]
            if key == 'family':
                for dataset in form.cleaned_data:
                    if len(dataset):
                        family_members.append(FamilyMember(**dataset))

            else:
                for field in form.cleaned_data.keys():
                    if field == 'mugshot': continue
                    setattr(refugee, field, form.cleaned_data[field])

        refugee.save()
        for member in family_members:
            member.refugee = refugee
            member.save()

        return HttpResponseRedirect(reverse('userena_signup_complete', kwargs={'username': user.username}))

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

class RefugeSpaceWishList(ListView):
    model = Application
    paginate_by = 10

    def get_queryset(self):
        if self.request.user.my_profile.type == 'R':
            return self.model._default_manager.filter(refugee=self.request.user.refugee)

        return self.model._default_manager.none()

    def get_context_data(self, **kwargs):
        context = super(RefugeSpaceWishList, self).get_context_data(**kwargs)
        context['status_list'] = APPLICATION_STATUS

        return context

class RefugeDetail(TemplateView):
    template_name = 'common/profile_detail.html'

    def post(self, request, *args, **kwargs):
        form = RefugeFamilyCreateForm(self.request.POST, self.request.FILES)
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        member = form.save(commit=False)
        member.refugee = self.request.user.refugee
        member.save()
        return self.render_to_response(self.get_context_data())

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, form=None, **kwargs):
        context = super(RefugeDetail, self).get_context_data(**kwargs)
        context['profile'] = self.request.user.my_profile
        if hasattr(self.request.user, 'refugee'):
            context['citizen'] = self.request.user.refugee
            context['family_members'] = self.request.user.refugee.\
                                            familymember_set.order_by('pk').all()
            context['family_form'] = form or RefugeFamilyCreateForm()
        context['gender_list'] = GENDER[1:]
        context['countries_list'] = countries
        return context

class RefugeDetailUpdate(ProcessFormView):
    template_name = 'common/profile_detail.html'

    def get(self, request, *args, **kwargs):
        raise PermissionDenied

    def post(self, request, *args, **kwargs):
        if self.kwargs.get('type') == 'family':
            family = FamilyMember.objects.filter(pk=self.request.POST.get('id'),
                        refugee=self.request.user.refugee).first()
            if len(self.request.FILES):
                form = RefugeFamilyImageForm(self.request.POST, self.request.FILES,
                        instance=family)
            else:
                form = RefugeFamilyCreateForm(self.request.POST, instance=family)

        elif self.kwargs.get('type') == 'family-delete':
            family = FamilyMember.objects.filter(pk=self.request.POST.get('id'),
                        refugee=self.request.user.refugee).first()
            if family:
                family.delete()
                return JsonResponse({'success': True})
            return JsonResponse({'success': False})
        else:
            if len(self.request.FILES):
                form = RefugePersonalImageForm(self.request.POST, self.request.FILES,
                        instance=self.request.user.refugee)
            else:
                form = RefugePersonalDetailForm(self.request.POST,
                            instance=self.request.user.refugee)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        if self.kwargs.get('type') == 'family-create':
            member = form.save(commit=False)
            member.refugee = self.request.user.refugee
            member.save()
        else:
            model = form.save(commit=False)
            model.save()

            if hasattr(model, 'user'):
                url = model.user.my_profile.get_mugshot_url()
            elif model.image:
                url = model.image.url
            else:
                url = ''

            if len(self.request.FILES):
                return JsonResponse({'success': True, 'url': url})

        return JsonResponse({'success': True})

    def form_invalid(self, form):
        return JsonResponse({'success': False,'errors': form.errors})

