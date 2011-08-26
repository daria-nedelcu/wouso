from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin
admin.autodiscover()
import wouso.games

urlpatterns = patterns('',
    (r'^$', 'wouso.interface.views.homepage'),
    (r'^top/toptype/(\d)/sortcrit/(\d)/page/(\d+)/$', 'interface.top.views.gettop'),
    # toptype = 0 means overall top
    # toptype = 1 means top for 1 week
    # sortcrit = 0 means sort by points descending
    # sortcrit = 1 means sort by progress descending
    # sortcrit = 2 means sort by last_seen descending

    (r'^user/login/$', 'django.contrib.auth.views.login'),
    (r'^user/logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}),
    (r'^user/profile/(?P<id>\d*)/$', 'wouso.interface.profile.views.user_profile'),
    (r'^user/profile/(?P<id>\d*)/(?P<page>\d*)/$', 'wouso.interface.profile.views.user_profile'),
    (r'^user/profile/$', 'wouso.interface.profile.views.profile'),

    (r'^search/$', 'wouso.interface.views.search'),
    (r'^instantsearch/$', 'wouso.interface.views.instantsearch'),
    (r'^searchone/$', 'wouso.interface.views.searchone'),
    (r'^staticpage/(\d+)/$', 'wouso.interface.views.staticpage'),

    # Messaging
    (r'^m/', include('wouso.interface.messaging.urls')),

    # Games
    (r'^g/', include('wouso.games.urls')),

    # Admin related
    (r'^cpanel/', include('interface.cpanel.urls')),
    (r'^admin/', include(admin.site.urls)),
    (r'^admin/djangologdb/', include('djangologdb.urls')),

    # Static: not in a real deployment
    (r'^static/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT}),

)
