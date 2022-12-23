OCitySMap installation instructions
===================================

These instructions refer to software dependencies by using Ubuntu Bionic (18.04LTS)
package names. Minor adaptations might be needed for other distributions or for the
precise Debian or Ubuntu release you are using. They have been tested on several
x86_64 hosts.

If you are fine with running OCitySMap and MapOSMatic in a Vagrant virtual machine,
plese have a look at the MapOSMatic Vagrant repository:

https://github.com/hholzgra/maposmatic-vagrant

Note that this is mostly usefuly for personal development and small local test setups
only. For hosting a public service a Vagrant/Virtualbox virtualization setup may not
be stable and performant enough though.

ITs provisioning shell scripts may also help as a guide to install things on a
non-virtual machine though.

 ## Installation of required packages

```bash
sudo apt-get --yes install postgresql postgresql-contrib postgis osm2pgsql \
                           python3-mapnik python3-cairo python3-psycopg2 \
			   python3-shapely python3-natsort python3-colour \
			   python3-gdal python3-pluginbase python3-gpxpy \
			   python3-gi-cairo gir1.2-pango-1.0 gir1.2-rsvg-2.0 \
                           python3-qrcode python3-pip

sudo pip3 install utm
```

 ## Creation of a new PostgreSQL user

```bash
sudo --user=postgres createuser --pwprompt --superuser --createdb maposmatic
```
Enter the password twice (we later use ``secret`` as example password).

 ## Creation of the database

```bash
sudo --user=postgres createdb --encoding=UTF8 --locale=en_US.UTF-8 \
                              --template=template0 --owner=maposmatic maposmatic
```
(see also http://wiki.openstreetmap.org/wiki/Mapnik/PostGIS)

You can now try to connect to the database, using:

```bash
psql --host=localhost --username=maposmatic maposmatic
```
If it doesn't work, fix your configuration.

 ## Enable PostGIS and Hstore extensions on the database

```bash
echo "CREATE EXTENSION postgis;" | sudo --user=postgres psql --dbname=maposmatic
echo "ALTER TABLE geometry_columns OWNER TO maposmatic;" | sudo --user=postgres psql --dbname=maposmatic
echo "ALTER TABLE spatial_ref_sys OWNER TO maposmatic;" | sudo --user=postgres psql --dbname=maposmatic
echo "CREATE EXTENSION hstore;" | sudo --user=postgres psql --dbname=maposmatic
```
 
 ## Download OSM data

We use the Luxembourg country extract here, using the country extrat server provided by GeoFabrik, Germany:

```bash
wget http://download.geofabrik.de/europe/luxembourg-latest.osm.pbf
```

 ## Import the OSM data with ``osm2pgsql``

``` bash
    osm2pgsql --create --slim --database=maposmatic --merc --username=maposmatic \
             --password --host=localhost --hstore-all luxembourg-latest.osm.pbf
```
    
If you have a lot of RAM, remove ``--slim``, it will make the import faster. If you
miss RAM (and have a lot of time available) you can also use the ``--cache`` option
together with ``-s``. (See also ``osm2pgsql -h``).

If you want to add other OSM DB files, replace the ``--create`` option with the
``--append`` option for the subsequent files you are adding: if you keep the
``--create`` option, it will erase and overwrite any previous GIS data you may
have. For example:

```bash
wget http://download.geofabrik.de/europe/france/ile-de-france-latest.osm.pbf

osm2pgsql --append --slim --database=maposmatic --merc --username=maposmatic \
          --password --host=localhost --hstore-all ile-de-france-latest.osm.pbf
```

## Install Openstreetmap Carto style

TODO, for now please refer to the original OSM Carto install file:

https://github.com/gravitystorm/openstreetmap-carto/blob/master/INSTALL.md

## Installation of OCitySMap

### Download the source code

If you have `git` installed, you can clone the project repository directly:

```bash
git clone git://git.savannah.nongnu.org/maposmatic/ocitysmap.git
cd ocitysmap
```

Or you can download the project source code as a ZIP archive from GitHub without
having to have `git` installed:

```bash 
wget https://codeload.github.com/hholzgra/ocitysmap/zip/master --output-document=ocitysmap.zip
unzip ocitysmap.zip
cd ocitysmap-master
```

###  Configuration file

Create a ``~/.ocitysmap.conf`` configuration file, modeled after the provided
``ocitysmap.conf.dist`` file:

```bash
cp ocitysmap.conf.dist ~/.ocitysmap.conf
```

### Run the OCitySMap renderer on the command line

E.g. for the example data imports above:

```bash
./render.py --title="Ceci n'est pas Paris" --osmid=-411354  # Contern, LU
./render.py --title "Ceci n'est pas Paris" --osmid=-943886  # Chevreuse, FR
```

The osmid is given as a negative number here as we are referring
to adminstrative boundary relations that have been converted to
single object polygon ways during the import.




Appendix A:  Installation of maposmatic-printable stylesheet
------------------------------------------------------------

a. Copy stylesheet/maposmatic-printable/symbols/* (i.e. all files in symbols/ directory) into mapnik2-osm/symbols/ directory.

b. Add absolute path to file stylesheet/maposmatic-printable/osm.xml into ~/.ocitysmap.conf.

c. Configure the stylesheet with database parameters and relevant  directories:

```bash
cd stylesheet/maposmatic-printable/

python ./generate_xml.py --dbname maposmatic --host 'localhost' \
         --user maposmatic --port 5432 \
         --password 'secret' \
         --world_boundaries mapnik2-osm/world_boundaries \
         --symbols mapnik2-osm/symbols
```

