from datetime import timedelta
from django.conf import settings
import ipaddress


def get_client_ip(request):
	"""Return the client's IP address from the request."""
	x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
	if x_forwarded_for:
		ip = x_forwarded_for.split(',')[0].strip()
	else:
		ip = request.META.get('REMOTE_ADDR')
	return ip or ''


def is_on_university_wifi(request):
	"""
	CIS-Prox Network Gatekeeping: Verify client is on authorized campus subnet.
	
	During development (`DEBUG=True`) allow check-ins from any network so
	you can test from devices that cannot reach the local LAN. In
	production, the IP-prefix check is used against configured campus subnets.
	"""
	# Allow when in development mode so check-in UI is not blocked while testing
	if getattr(settings, 'DEBUG', False):
		return True

	ip = get_client_ip(request)
	if not ip:
		return False
	
	# Get allowed campus subnets from settings; defaults to 192.168.0.0/16 (typical private range)
	allowed_subnets = getattr(settings, 'CAMPUS_WIFI_SUBNETS', ['192.168.0.0/16'])
	
	try:
		client_ip = ipaddress.ip_address(ip)
		for subnet_str in allowed_subnets:
			subnet = ipaddress.ip_network(subnet_str, strict=False)
			if client_ip in subnet:
				return True
	except ValueError:
		# Invalid IP format
		pass
	
	return False


def get_campus_subnets():
	"""Return the list of authorized campus Wi-Fi subnets."""
	return getattr(settings, 'CAMPUS_WIFI_SUBNETS', ['192.168.0.0/16'])


# ============================================================================
# PRIVACY & CLASSMATE VERIFICATION UTILITIES
# ============================================================================

def get_user_section(user):
	"""
	Get the section of a user from their StudentPresence record.
	Returns the Section object or None if user has no section.
	"""
	from presence_app.models import StudentPresence
	try:
		presence = StudentPresence.objects.get(student=user)
		return presence.section
	except StudentPresence.DoesNotExist:
		return None


def are_classmates(user1, user2):
	"""
	Check if two users are classmates (belong to the same section).
	
	Args:
		user1: User object
		user2: User object
	
	Returns:
		bool: True if both users are in the same section, False otherwise
	"""
	section1 = get_user_section(user1)
	section2 = get_user_section(user2)
	
	# Both must have sections and they must match
	if section1 and section2:
		return section1.id == section2.id
	
	return False


def can_view_user_profile(viewer, target):
	"""
	Determine if a viewer can see a target user's profile based on privacy rules.
	
	Privacy Rules:
	- PUBLIC: Visible to everyone logged in
	- FRIENDS_ONLY (Custom): Visible only to classmates
	- ONLY_ME: Never visible to others
	
	Args:
		viewer: Requesting User object
		target: Target User object to check privacy for
	
	Returns:
		bool: True if viewer can see target's profile, False otherwise
	"""
	from presence_app.models import UserProfile
	
	# Can always view own profile
	if viewer.id == target.id:
		return True
	
	try:
		target_profile = target.profile
	except UserProfile.DoesNotExist:
		# No profile = no public visibility
		return False
	
	# RULE 1: ONLY_ME - Never visible to others
	if target_profile.privacy_level == UserProfile.PRIVACY_ONLY_ME:
		return False
	
	# RULE 2: PUBLIC - Visible to everyone logged in
	if target_profile.privacy_level == UserProfile.PRIVACY_PUBLIC:
		return True
	
	# RULE 3: FRIENDS_ONLY (Custom) - Visible only to classmates
	if target_profile.privacy_level == UserProfile.PRIVACY_FRIENDS_ONLY:
		return are_classmates(viewer, target)
	
	return False


def get_visible_users_queryset(requesting_user, base_queryset=None):
	"""
	Filter a QuerySet of users based on privacy rules.
	
	This enforces privacy at the database level to prevent unauthorized data exposure.
	
	Args:
		requesting_user: The user making the request
		base_queryset: Initial QuerySet of User objects to filter
				If None, uses User.objects.all()
	
	Returns:
		QuerySet: Filtered users that the requesting_user can see
	"""
	from django.contrib.auth.models import User
	from django.db.models import Q
	from presence_app.models import UserProfile, StudentPresence
	
	if base_queryset is None:
		base_queryset = User.objects.all()
	
	# Get requesting user's section
	try:
		searcher_section = StudentPresence.objects.get(student=requesting_user).section
	except StudentPresence.DoesNotExist:
		searcher_section = None
	
	# Build Q objects for privacy rules
	# PUBLIC users are always visible
	public_users = Q(profile__privacy_level=UserProfile.PRIVACY_PUBLIC)
	
	# ONLY_ME users are never visible
	# (We'll exclude these with ~Q)
	only_me_users = Q(profile__privacy_level=UserProfile.PRIVACY_ONLY_ME)
	
	# CUSTOM users are visible only to classmates
	if searcher_section:
		custom_visible = Q(
			profile__privacy_level=UserProfile.PRIVACY_FRIENDS_ONLY,
			student_presence__section=searcher_section
		)
	else:
		# Non-student searchers can't see custom profiles
		custom_visible = Q(pk__in=[])  # Empty queryset
	
	# Combine: PUBLIC OR (CUSTOM AND CLASSMATES)
	visible_users = base_queryset.filter(public_users | custom_visible).exclude(only_me_users)
	
	return visible_users
