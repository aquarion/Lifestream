Lifestream
----------

Lifestream is a series of scripts to grab data from places and dump it into a
database.

Lifestream is an AJAX-based box that updates this on a web page in real time.

Lifestream is a wordpress plugin to make that work, too.


h2. How to make it go:

* Use the schema to create a database
* copy dbconfig.ini.example to lose the example bit
* edit it to contain real live database details
* Each import script accepts a username as a parameter
   pipe the output of the script to the database
* eg:  twitter.py [Lifestream "Type"] [Twitter Username] [Twitter Password]
* Cron this, because typing it every so often is dull.

* Install the web dir somewhere accessible, edit the conn.php file with database stuff
* Edit the wordpress plugin to be able to find it.
* Complain when it doesn't work.
