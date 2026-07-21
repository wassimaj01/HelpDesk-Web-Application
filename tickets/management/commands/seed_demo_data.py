from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction

from tickets.models import (
    Lieu,
    LieuService,
    ProblemType,
    Service,
    Ticket,
    UserProfile,
)

GROUP_NAMES = ['Employee', 'IT_Admin', 'IT_Operator', 'Super_Admin']

DEFAULT_PASSWORD = 'password123'


class Command(BaseCommand):
    help = 'Seeds the database with demo data for the GPI ticketing application.'

    @transaction.atomic
    def handle(self, *args, **options):
        groups = self._create_groups()
        users = self._create_users(groups)
        lieux = self._create_lieux()
        services = self._create_services()
        lieu_services = self._create_lieu_services(lieux, services)
        self._create_profiles(users, lieu_services)
        problem_types = self._create_problem_types(users)
        self._create_sample_tickets(users, lieu_services, problem_types)

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))

    # ------------------------------------------------------------------
    def _create_groups(self):
        groups = {}
        for name in GROUP_NAMES:
            group, _ = Group.objects.get_or_create(name=name)
            groups[name] = group
        self.stdout.write(self.style.SUCCESS('Groups created.'))
        return groups

    def _create_users(self, groups):
        users = {}

        def get_or_create_user(username, email, group_name, is_staff=False, is_superuser=False):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'is_staff': is_staff,
                    'is_superuser': is_superuser,
                },
            )
            if created:
                user.set_password(DEFAULT_PASSWORD)
                user.save()
            if group_name:
                user.groups.add(groups[group_name])
            users[username] = user
            return user

        get_or_create_user(
            'superadmin', 'superadmin@gpi.local', 'Super_Admin',
            is_staff=True, is_superuser=True,
        )
        get_or_create_user('aziz', 'aziz@gpi.local', 'IT_Admin', is_staff=True)
        get_or_create_user('said', 'said@gpi.local', 'IT_Admin', is_staff=True)
        get_or_create_user('operator1', 'operator1@gpi.local', 'IT_Operator')
        get_or_create_user('operator2', 'operator2@gpi.local', 'IT_Operator')
        get_or_create_user('employee1', 'employee1@gpi.local', 'Employee')

        self.stdout.write(self.style.SUCCESS('Users created.'))
        return users

    def _create_lieux(self):
        lieux = {}
        for name in ['Siège', 'Agence Casablanca']:
            lieu, _ = Lieu.objects.get_or_create(name=name)
            lieux[name] = lieu
        self.stdout.write(self.style.SUCCESS('Lieux created.'))
        return lieux

    def _create_services(self):
        services = {}
        service_defs = [
            ('Adhésion', 'ADHESION'),
            ('Contrôle dentaire', 'CONTROLE_DENTAIRE'),
            ('Informatique', 'INFORMATIQUE'),
        ]
        for name, code in service_defs:
            service, _ = Service.objects.get_or_create(code=code, defaults={'name': name})
            services[name] = service
        self.stdout.write(self.style.SUCCESS('Services created.'))
        return services

    def _create_lieu_services(self, lieux, services):
        combinations = [
            ('Siège', 'Informatique'),
            ('Agence Casablanca', 'Adhésion'),
            ('Agence Casablanca', 'Contrôle dentaire'),
        ]
        lieu_services = {}
        for lieu_name, service_name in combinations:
            lieu_service, _ = LieuService.objects.get_or_create(
                lieu=lieux[lieu_name], service=services[service_name]
            )
            lieu_services[(lieu_name, service_name)] = lieu_service
        self.stdout.write(self.style.SUCCESS('Lieu-Service combinations created.'))
        return lieu_services

    def _create_profiles(self, users, lieu_services):
        siege_info = lieu_services[('Siège', 'Informatique')]
        casa_adhesion = lieu_services[('Agence Casablanca', 'Adhésion')]

        profile_defs = [
            ('superadmin', siege_info),
            ('aziz', siege_info),
            ('said', siege_info),
            ('operator1', siege_info),
            ('operator2', siege_info),
            ('employee1', casa_adhesion),
        ]
        for username, lieu_service in profile_defs:
            UserProfile.objects.get_or_create(
                user=users[username], defaults={'lieu_service': lieu_service}
            )
        self.stdout.write(self.style.SUCCESS('User profiles created.'))

    def _create_problem_types(self, users):
        aziz = users['aziz']
        said = users['said']

        problem_type_defs = [
            (
                'Problème de connexion Internet',
                ProblemType.Category.NETWORK_TELECOM_HELPDESK,
                aziz,
            ),
            (
                'Problème téléphone / réseau',
                ProblemType.Category.NETWORK_TELECOM_HELPDESK,
                aziz,
            ),
            (
                'Problème imprimante / scanner',
                ProblemType.Category.NETWORK_TELECOM_HELPDESK,
                aziz,
            ),
            (
                'Mot de passe / accès utilisateur',
                ProblemType.Category.NETWORK_TELECOM_HELPDESK,
                aziz,
            ),
            (
                'Erreur application métier',
                ProblemType.Category.APPLICATION_DATABASE_SOFTWARE,
                said,
            ),
            (
                'Problème base de données',
                ProblemType.Category.APPLICATION_DATABASE_SOFTWARE,
                said,
            ),
            (
                "Problème logiciel d'exploitation",
                ProblemType.Category.APPLICATION_DATABASE_SOFTWARE,
                said,
            ),
            (
                'Problème serveur applicatif',
                ProblemType.Category.APPLICATION_DATABASE_SOFTWARE,
                said,
            ),
        ]

        problem_types = {}
        for label, category, responsible_admin in problem_type_defs:
            problem_type, _ = ProblemType.objects.get_or_create(
                label=label,
                defaults={'category': category, 'responsible_admin': responsible_admin},
            )
            problem_types[label] = problem_type

        self.stdout.write(self.style.SUCCESS('Problem types created.'))
        return problem_types

    def _create_sample_tickets(self, users, lieu_services, problem_types):
        employee1 = users['employee1']
        requester_lieu_service = employee1.profile.lieu_service

        sample_defs = [
            (
                'TCK-0001',
                'Problème de connexion Internet',
                "Impossible de se connecter au réseau depuis ce matin.",
            ),
            (
                'TCK-0002',
                'Erreur application métier',
                "L'application de liquidation affiche une erreur au démarrage.",
            ),
        ]

        for reference, problem_label, description in sample_defs:
            problem_type = problem_types[problem_label]
            if Ticket.objects.filter(reference=reference).exists():
                continue
            Ticket.objects.create(
                reference=reference,
                problem_type=problem_type,
                description=description,
                category=problem_type.category,
                status=Ticket.Status.CREATED,
                created_by=employee1,
                requester_lieu_service=requester_lieu_service,
                responsible_admin=problem_type.responsible_admin,
            )

        self.stdout.write(self.style.SUCCESS('Sample tickets created.'))
