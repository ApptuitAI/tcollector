# Don't check stuff, we know exactly what we want.
%undefine __check_files

%global tcollectordir /usr/local/xcollector
%global collectorsdir %{tcollectordir}/collectors
%global rootdir       %{_topdir}/../..
%global eosdir        %{rootdir}/eos
%global srccollectors %{rootdir}/collectors
%global py2_sitelib   /usr/lib/python2.7/site-packages
%global grokexpdir    %{tcollectordir}/grok_exporter
%global grokexprootdir %{rootdir}/grok_exporter

# Don't terminate the build because we are shipping grok binaries.
# On incompatible archs other collectors in xcollector will continue to work
%define _binaries_in_noarch_packages_terminate_build   0

BuildArch:      @RPM_TARGET@
Name:           xcollector
Group:          System/Monitoring
Version:        @PACKAGE_VERSION@
Release:        @RPM_REVISION@
Distribution:   buildhash=@GIT_FULLSHA1@
License:        LGPLv3+
Summary:        XCollector - Data collection agent for apptuit.ai
URL:            http://apptuit.ai/xcollector.html
Provides:       xcollector = @PACKAGE_VERSION@-@RPM_REVISION@_@GIT_SHORTSHA1@
Packager:       XCollector Maintainers <hello+xcollector@apptuit.ai>
Requires:       initscripts
Requires:       python(abi) >= @PYTHON_VERSION@
Requires:       python-devel
Requires:       MySQL-python
Requires:       python-requests
Requires:       PyYAML

%description
Variant of tcollector that pushes metrics to Apptuit.AI
The xcollector package includes the basic collector and
all of the dependencies these collectors need.

%install
mkdir -p %{buildroot}/%{collectorsdir}/0/
mkdir -p %{buildroot}/etc/init.d/

# set homedir in init script
%{__perl} -pe "s|HOMEDIR|%{tcollectordir}|;" -i %{rootdir}/rpm/initd.sh
# Install the init.d
%{__install} -m 0755 -D %{rootdir}/rpm/initd.sh %{buildroot}/etc/init.d/xcollector

# Install Base files
mkdir -p %{buildroot}%{tcollectordir}/conf/
mkdir -p %{buildroot}%{tcollectordir}/collectors/lib/
mkdir -p %{buildroot}%{tcollectordir}/collectors/etc/
mkdir -p %{buildroot}%{grokexpdir}/patterns/
%{__install} -m 0755 -D %{grokexprootdir}/grok_exporter %{buildroot}%{grokexpdir}/grok_exporter
%{__install} -m 0755 -D %{grokexprootdir}/patterns/* %{buildroot}%{grokexpdir}/patterns/
%{__install} -m 0755 -D %{rootdir}/conf/* %{buildroot}%{tcollectordir}/conf/
%{__install} -m 0755 -D %{srccollectors}/__init__.py %{buildroot}%{tcollectordir}/collectors/
%{__install} -m 0755 -D %{srccollectors}/lib/*.py %{buildroot}%{tcollectordir}/collectors/lib/
%{__install} -m 0755 -D %{srccollectors}/etc/*.py %{buildroot}%{tcollectordir}/collectors/etc/
%{__install} -m 0755 -D %{rootdir}/tcollector.py %{buildroot}%{tcollectordir}/xcollector.py
%{__install} -m 0755 -D %{rootdir}/grok_scraper.py %{buildroot}%{tcollectordir}/grok_scraper.py

# Install Collectors
%{__install} -m 0755 -D %{srccollectors}/0/*.py %{buildroot}%{collectorsdir}/0/

# Install EOS files
%{__install} -m 0755 -D %{eosdir}/collectors/agent*.sh %{buildroot}/%{collectorsdir}/0/
%{__install} -m 0755 -D %{eosdir}/collectors/eos.py %{buildroot}/%{collectorsdir}/0/
mkdir -p %{buildroot}/usr/bin/
%{__install} -m 0755 -D %{eosdir}/tcollector %{buildroot}/usr/bin/
mkdir -p %{buildroot}/%{py2_sitelib}/
%{__install} -m 0755 -D %{eosdir}/tcollector_agent.py %{buildroot}/%{py2_sitelib}/


%files
%dir %{tcollectordir}
%attr(755, -, -) /etc/init.d/xcollector
%{tcollectordir}/collectors/__init__.py
%dir %{tcollectordir}/collectors/lib/
%{tcollectordir}/collectors/lib/__init__.py
%{tcollectordir}/collectors/lib/utils.py
#%{tcollectordir}/collectors/lib/hadoop_http.py
%dir %{tcollectordir}/collectors/etc/
%{tcollectordir}/collectors/etc/__init__.py
%{tcollectordir}/collectors/etc/config.py
%{tcollectordir}/collectors/etc/yaml_conf.py
#%{tcollectordir}/collectors/etc/flume_conf.py
#%{tcollectordir}/collectors/etc/g1gc_conf.py
#%{tcollectordir}/collectors/etc/graphite_bridge_conf.py
%{tcollectordir}/collectors/etc/grok_scraper_conf.py
#%{tcollectordir}/collectors/etc/jolokia_conf.py
%{tcollectordir}/collectors/etc/mysqlconf.py
%{tcollectordir}/collectors/etc/metric_naming.py
#%{tcollectordir}/collectors/etc/postgresqlconf.py
#%{tcollectordir}/collectors/etc/udp_bridge_conf.py
#%{tcollectordir}/collectors/etc/zabbix_bridge_conf.py
%{tcollectordir}/collectors/etc/udp_bridge_conf.py
%{tcollectordir}/conf/grok.yml %config(noreplace)
%{tcollectordir}/conf/grok_nginx.yml %config(noreplace)
%{tcollectordir}/conf/grok_tomcat.yml %config(noreplace)
%{tcollectordir}/conf/mysql.yml %config(noreplace)
%{tcollectordir}/conf/memcached_metrics.yml %config(noreplace)
%{tcollectordir}/conf/mysql_metrics.yml %config(noreplace)
%{tcollectordir}/conf/node_metrics.yml %config(noreplace)
%{tcollectordir}/conf/xcollector.yml %config(noreplace)
%{tcollectordir}/xcollector.py
%{tcollectordir}/grok_scraper.py
%{tcollectordir}/collectors/0/dfstat.py
%{tcollectordir}/collectors/0/ifstat.py
%{tcollectordir}/collectors/0/iostat.py
%{tcollectordir}/collectors/0/netstat.py
%{tcollectordir}/collectors/0/procnettcp.py
%{tcollectordir}/collectors/0/procstats.py
%{tcollectordir}/collectors/0/udp_bridge.py
#%{tcollectordir}/collectors/0/smart_stats.py
%{tcollectordir}/collectors/0/mysql.py
%{tcollectordir}/collectors/0/memcache.py
%{grokexpdir}/grok_exporter
%{grokexpdir}/patterns/aws
%{grokexpdir}/patterns/bacula
%{grokexpdir}/patterns/bro
%{grokexpdir}/patterns/exim
%{grokexpdir}/patterns/firewalls
%{grokexpdir}/patterns/grok-patterns
%{grokexpdir}/patterns/haproxy
%{grokexpdir}/patterns/java
%{grokexpdir}/patterns/junos
%{grokexpdir}/patterns/linux-syslog
%{grokexpdir}/patterns/mcollective
%{grokexpdir}/patterns/mcollective-patterns
%{grokexpdir}/patterns/mongodb
%{grokexpdir}/patterns/nagios
%{grokexpdir}/patterns/postgresql
%{grokexpdir}/patterns/rails
%{grokexpdir}/patterns/redis
%{grokexpdir}/patterns/ruby

%pre
if [ "$1" = "2" ]; then
    # stop previous version of xcollector service before starting upgrade
    service xcollector stop
fi

%post
if [ ! -L "/etc/xcollector" ]
then
  ln -s %{tcollectordir}/conf /etc/xcollector
fi
if [ ! -L "%{tcollectordir}/collectors/0/grok_nginx.py" ]
then
  ln -s %{tcollectordir}/grok_scraper.py %{tcollectordir}/collectors/0/grok_nginx.py
fi
if [ ! -L "%{tcollectordir}/collectors/0/grok_tomcat.py" ]
then
  ln -s %{tcollectordir}/grok_scraper.py %{tcollectordir}/collectors/0/grok_tomcat.py
fi
if [ ! -d "/var/run/xcollector" ]
then
  mkdir -p "/var/run/xcollector"
fi
if [ ! -d "/var/log/xcollector" ]
then
  mkdir -p "/var/log/xcollector"
fi

XCOLLECTOR_USER="xcollector"
XCOLLECTOR_GROUP="xcollector"

if [ -z "$(getent group $XCOLLECTOR_GROUP)" ]; then
  groupadd --system $XCOLLECTOR_GROUP
else
  echo "Group [$XCOLLECTOR_GROUP] already exists"
fi

if [ -z "$(id $XCOLLECTOR_USER)" ]; then
  useradd --system --home-dir /usr/local/xcollector --no-create-home \
  -g $XCOLLECTOR_GROUP --shell /sbin/nologin $XCOLLECTOR_USER
else
  echo "User [$XCOLLECTOR_USER] already exists"
fi

chown -R $XCOLLECTOR_USER.$XCOLLECTOR_GROUP /usr/local/xcollector
chown -R $XCOLLECTOR_USER.$XCOLLECTOR_GROUP /var/run/xcollector
chown -R $XCOLLECTOR_USER.$XCOLLECTOR_GROUP /var/log/xcollector

chkconfig --add xcollector
grep PASTE_ACCESS_TOKEN_HERE /etc/xcollector/xcollector.yml >/dev/null || service xcollector start

%preun
if [ "$1" = "0" ]; then
    # stop service before starting the uninstall
    service xcollector stop
    chkconfig --del xcollector
fi

%postun
# $1 --> if 0, then it is a deinstall
# $1 --> if 1, then it is an upgrade
if [ $1 -eq 0 ] ; then
    # This is a removal, not an upgrade
    #  $1 versions will remain after this uninstall

    # Clean up collectors
    rm -f /etc/init.d/xcollector
    rm -f /etc/xcollector

    userdel xcollector
fi
