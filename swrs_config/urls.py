from django.contrib import admin
from django.urls import path
from presence_app import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('enroll/', views.enroll, name='enroll'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/upload-picture/', views.upload_profile_picture, name='upload_profile_picture'),
    path('profile/<str:username>/', views.profile_view, name='profile_view'),
    path('attendance/', views.attendance_dashboard, name='attendance_dashboard'),
    path('activity/signin/', views.activity_signin, name='activity_signin'),
    path('activity/signout/', views.activity_signout, name='activity_signout'),
    path('activity/signout/<int:activity_id>/', views.activity_signout, name='activity_signout_specific'),
    path('cleaning/manage/', views.admin_cleaning_manage, name='admin_cleaning_manage'),
    path('cleaning/force-signout/<int:activity_id>/', views.admin_force_signout, name='admin_force_signout'),
    # Instructor routes
    path('instructor/dashboard/', views.instructor_dashboard, name='instructor_dashboard'),
    path('instructor/reports/', views.instructor_reports, name='instructor_reports'),
    path('instructor/frc/mark/<int:student_id>/', views.instructor_mark_frc, name='instructor_mark_frc'),
    path('instructor/signout/manage/', views.instructor_manage_signout, name='instructor_manage_signout'),
    path('instructor/signout/adjust/<int:activity_id>/', views.instructor_adjust_signout, name='instructor_adjust_signout'),
    # Instructor Admin Panel - Manage Students & Rooms
    path('instructor/admin/', views.instructor_admin, name='instructor_admin'),
    path('instructor/admin/student/<int:student_id>/', views.instructor_admin_student_detail, name='instructor_admin_student_detail'),
    # Admin System Dashboard (SUPERUSER ONLY)
    path('admin-dashboard/', views.admin_system_dashboard, name='admin_system_dashboard'),
    # Admin User Management (SUPERUSER ONLY)
    path('admin-users/', views.admin_user_management, name='admin_user_management'),
    # Instructor Account Management (ADMIN ONLY - SEPARATE FROM DJANGO ADMIN)
    path('manage-instructors/', views.admin_instructor_management, name='admin_instructor_management'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('signin/', views.sign_in, name='sign_in_post'),
    path('signin/<int:room_id>/', views.sign_in, name='sign_in'),
    path('signout/', views.sign_out, name='sign_out'),
    path('search/', views.peer_search, name='peer_search'),
    path('api/search-peers/', views.search_peers_api, name='search_peers_api'),
    path('api/search/peers/', views.search_peers_api, name='search_peers_api_alt'),
    path('api/privacy/allowed-friends/', views.allowed_friends_api, name='allowed_friends_api'),
    path('api/privacy/add-friend/', views.add_friend_api, name='add_friend_api'),
    path('api/privacy/remove-friend/', views.remove_friend_api, name='remove_friend_api'),
    path('privacy/update/', views.privacy_update, name='privacy_update'),
    path('privacy/instructor/update/', views.instructor_privacy_update, name='instructor_privacy_update'),
    # CIS-Prox Presence & Peer Discovery
    path('presence/signin/', views.presence_signin, name='presence_signin'),
    path('presence/signout/', views.presence_signout, name='presence_signout'),
    path('presence/search/', views.presence_search, name='presence_search'),
    path('presence/dashboard/', views.presence_dashboard, name='presence_dashboard'),
    # Laboratory History (Automatic Exit Tracking)
    path('laboratory/history/', views.laboratory_history, name='laboratory_history'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
