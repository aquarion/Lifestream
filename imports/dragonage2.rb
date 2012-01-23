
if ARGV.length != 2
  throw "Usage: bioware_social.rb [UID] [NID] "+ARGV.length.to_s
end

url = "http://social.bioware.com/playerprofile.php?nid=%s" % ARGV[0] 

url = "http://social.bioware.com/%s/&v=bw_games&game=dragonage2_pc&pid=%s&display=achievements" % [ARGV[0], ARGV[1]]

#engine = :watir
engine = :celerity

require 'digest/md5'

def debug_log message
  #puts message
end

# DB Setup
require "rubygems"
require "ini"
require File.dirname(__FILE__)+"/../lib/jdbcmysql"
ini = Ini.load(File.dirname(__FILE__)+"/../dbconfig.ini")
cnf = ini['database']
db = JdbcMysql.new(cnf['hostname'], cnf['username'],cnf['password'], cnf['database'])

biowarecnf = ini['bioware']
USERNAME=biowarecnf['username']
PASSWORD=biowarecnf['password']


debug_log "Start your engines"
if engine == :watir
  require "watir"
  b = Watir::Browser.start url
  
  
  def b.set_bool_preference(key, value)
    jssh_command = "var prefs =
    Components.classes[\"@mozilla.org/preferences-service;1\"].getService(Components.interfaces.nsIPrefBranch);"
    jssh_command += " prefs.setBoolPref(\"#{key}\", #{value});"
    $jssh_socket.send("#{jssh_command}\n", 0)
    read_socket()
  end

elsif engine == :celerity
    
  require "celerity"
  
  b = Celerity::Browser.start url
  
end

#b = Celerity::Browser.start url

if b.text.include? "This site contains user generated content"
  debug_log "Submiting language form"
  r = b.radio(:name, "lang_id")
  r.set(1);
  
  if engine == :watir
     b.form(:action, "language.php").submit
  elsif engine == :celerity
     b.button.click
  end
 
end

debug_log "Logging in"
b.text_field(:name, "email").value = USERNAME
b.text_field(:name, "password").value = PASSWORD
b.button(:value, "Login").click


query = 'insert delayed ignore into lifestream (`id`, `type`, `systemid`, `title`, `date_created`, `image`, `url`, `source`) values (0, "gaming", ?, ?, NOW(), ?, ?, "dragon age 2");'   
root = "http://social.bioware.com";        

#achievements = b.div(:class, "unlocked_outer_left");#

#if not achievements.respond_to?('each')
#  achievements = [achievements]
#end

if b.text.include? "Invalid login details."
	throw "Login failed"
end

debug_log "Found Divs"
b.divs.each do |div|
  if div.attribute_value("class") == "unlocked_outer_left" or div.attribute_value("class") == "unlocked_outer_right"
    achievement = div
    image = root+achievement.image.src
    text  = achievement.div(:class, "unlocked_title").text
    sysid = image.split("/")[-1].split(".")[0]
    
    debug_log "This is %s" % text
    
    params =  [sysid, text, image, url]
    
    #puts text
    
    db.preparedQuery(query,params)
  end
end


if engine == :watir
  b.set_bool_preference("javascript.enabled", true)
elsif engine == :celerity
  b.webclient.setJavaScriptEnabled(true)
end
