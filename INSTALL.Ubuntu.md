Quickstart ocitysmap installation on Ubuntu
===========================================

This is a quickstart guide to install ocitysmap on Ubuntu.
It has been tested on a fresh install of a Yakkety Yak edition (16.10). It doesn't work on older Ubuntu releases: on theses ones, if mapnik3 could be available, python-mapnik is not compiled with support for Cairo.

This guide should be OK in the next Debian release (Stretch).

General
-------

```bash
dpkg-reconfigure locales # choose "All locales" or only locales that suits your needs
# needed tools
apt install git wget
# base dependencies
apt install python-mapnik python-psycopg2 python-gdal python-gtk2 python-cairo python-shapely
# database
apt install postgresql-9.5-postgis-2.2 postgresql-contrib-9.5 osm2pgsql
```

Database creation
-----------------

```bash
# create database
su postgres
createuser -P -S -D -R gis
# give a password to this user and note it
createdb -E UTF8 -O gis gis
psql -c "CREATE EXTENSION postgis;" -d gis
psql -c "CREATE EXTENSION hstore;" -d gis
exit
```

Main openstreetmap theme
------------------------

```bash
apt install openstreetmap-carto
# Download OpenStreetMap data files from Internet? Yes
# Name of the PostgreSQL database: gis
```

Later you could install other mapnik themes.

First import of OSM data
------------------------

```bash
cd /srv
mkdir data
cd data
# geofabrik provide many exports - choose the area that suits your needs
wget http://download.geofabrik.de/europe/france/bretagne-latest.osm.pbf
osm2pgsql -d gis -U gis -H localhost -W -k -s /srv/data/bretagne-latest.osm.pbf
```

If you covers a limited area you could create a crontab entry to update regularly your database with this download / import process. If you want to cover a large area or the whole world, you should manage this with a more clever process.

ocitysmap installation
----------------------

```bash
cd /srv
git clone https://gitlab.com/iggdrasil/ocitysmap.git

adduser gis
chown -R gis ocitysmap
su gis
cd ocitysmap
cp ocitysmap.conf.dist ~/.ocitysmap.conf

vim ~/.ocitysmap.conf
```

```ini
[datasource]
host=localhost
user=gis
password=the_db_passord_you_have_noted
dbname=gis

[rendering]
available_stylesheets: stylesheet_osm1

[stylesheet_osm1]
name: Default
description: The default OSM style
path: /usr/share/openstreetmap-carto/style.xml
```

Test it!

```bash
./render.py -t "My beautiful city" --osmid=-530636
```

Of course osmid must be an id of a city inside your area. You could search this id with https://nominatim.openstreetmap.org/ . The minus "-" before the id is not a typo, it is necessary.
