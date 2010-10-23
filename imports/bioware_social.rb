
if ARGV.length != 1
  throw "Usage: bioware_social.rb [NID] "+ARGV.length.to_s
end

url = "http://social.bioware.com/playerprofile.php?nid=%s" % ARGV[0] 


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


if b.text.include? "Please enter your date of birth:"
  debug_log "Submiting DOB form"
  d = b.select_list(:name, "dob_day")
  d.set 1
  d = b.select_list(:name, "dob_month")
  d.set "January"
  d = b.select_list(:name, "dob_year")
  d.set 1981
  
  if engine == :watir
    b.form(:action, "").submit
  elsif engine == :celerity
     b.button.click
  end
end

if engine == :watir
  b.set_bool_preference("javascript.enabled", false)
elsif engine == :celerity
  b.webclient.setJavaScriptEnabled(false)
end


query = 'insert delayed ignore into lifestream (`id`, `type`, `systemid`, `title`, `date_created`, `image`, `url`, `source`) values (0, ?, ?, ?, NOW(), ?, ?, "bioware");'   
root = "http://social.bioware.com";        

if b.text.include? "Select a Profile"

  b.links.each do |link|
    
    link.click
    
    
    b.images.each do |image|
    if image.class_name == "achievement_list_item"     
        sysid = Digest::MD5.hexdigest(image.src)
        
        params =  ["bioware", sysid, image.title, root+image.src, root+"/"+link.href]
        
        debug_log params.to_s
        debug_log query
        
        db.preparedQuery(query,params)
        
        
      end
    end
    

    b.back
    
  end

end

if engine == :watir
  b.set_bool_preference("javascript.enabled", true)
elsif engine == :celerity
  b.webclient.setJavaScriptEnabled(true)
end
