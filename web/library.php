<?PHP

define("IMAGE_ROOT", 'http://art.istic.net/iconography/');

function get_start_and_end_date_from_week ($w, $y) 
{ 

    $date = mktime(0,0,0,1,4,$y); // 4th Jan is always week 1

    $days = ($w-1)*7;

    $date += $days*(24*60*60);

    $d = date("N", $date) - 1;

    $from = $date - (($d) * A_DAY);
    $to   = $date + ((7-$d) * A_DAY) -1;

    return array($from, $to);


}    # function datefromweek 

function niceTime($from, $to = false, $shortform = false){

	if (!$to){
		$to = time();
	}

        if ($from > $to){
                $since = $from - $to;
        } else {
                $since = $to - $from;
        }

        // 60 // minute
        // 3600 = hour
        // 86400 = day
        // 604800 = week

        if ($shortform){
                $units = array ('sec','min','hr','day','wk','yr');
        } else {
                $units = array ('second','minute','hour','day','week','year');
        }

        if ($since < 60){
                $date = $since;
                $unit = $units[0];

        } elseif ($since < 4000){
                $date = round($since/60);
                $unit = $units[1];

        } elseif ($since < 82000){
                $date = round($since/3600);
                $unit = $units[2];

        } elseif ($since < 603800){
                $date = round($since/86400);
                $unit = $units[3];
                #$plus = " on ".date("jS M");

        } elseif ($since < 31440000){
                $date = round($since/604800);
                $unit = $units[4];

        } else {
                $date = round($since/(604800 * 52));
                #$date = " over a year";
                $unit = $units[5];
        }

        if ($date == 1 || $unit == ""){
                $date = $date." ".$unit;
        } else {
                $date = $date." ".$unit."s";
        }

        if (!$shortform){
                #$date .= " ".$plus;
        }

        #$date .= " (".$since.")";

        return $date;
}

function process_lifestream_item($row){
  
	$row['title'] = str_replace("â€“","–", $row['title']);
	$row['title'] = str_replace("â€”","–", $row['title']);

	$text = $row['title'];
	$row['originaltext'] = $row['title'];

	

	
	$row['content'] = twitterFormat($text);
	
	if(!$row['source']){
		$row['source'] = $row['type'];
	}

	switch ($row['type']) {
		
	case "lastfm":
		$icon = IMAGE_ROOT.'silk/music.png';
		break;
		
	case "gaming":
		$icon = IMAGE_ROOT.'silk/joystick.png';
		if ($row['source'] == "Champions Online"){
			$icon = IMAGE_ROOT.'games/ChampionsOnline.png';
			$row['url'] = "http://www.champions-online.com/character_profiles/user_characters/Jascain";
		} elseif ($row['source'] == "HeroStats"){

			$icon = IMAGE_ROOT.'games/city_of_heroes/Hero.png';
			$row['small_icon'] = IMAGE_ROOT.'games/cityofheroes.png';
			$row['url'] = "http://cit.cohtitan.com/profile/13610";

		} elseif ($row['source'] == "Raptr" && preg_match('#Champions Online! #', $text)){
			$row['content'] .= "#";
		} elseif ($row['source'] == "XLN Live Integration"){
			$icon = IMAGE_ROOT.'silk/controller.png';
			$row['url'] = "http://live.xbox.com/en-GB/profile/profile.aspx?pp=0&GamerTag=Jascain";
		} elseif (preg_match('#\#wow#', $text)){
			$row['source'] = "World of Warcraft";
			$icon = IMAGE_ROOT.'games/world_of_warcraft.png';

		}
		break;

	case "steam":
		$icon = IMAGE_ROOT.'games/steam.png';
		$row['small_image'] = IMAGE_ROOT.'games/steam_small.png';
		#$row['url'] = "http://steamcommunity.com/id/aquarion/";
		$row['title'] = "Achieved: ".$row['title'];
		break;

	case "apps":
	case "location":
	
		if(preg_match("#^I\S* \w* a YouTube video#", $row['content'])){
			$icon = IMAGE_ROOT.'silk/film_add.png';
			$row['image'] = $icon;
			$match = preg_match("#I\S* \w* a YouTube video -- (.*?) (http.*)#", $row['originaltext'], $matches);
			
			$row['content'] = sprintf('<a href="%s">%s</a>', $matches[2], $matches[1]);
			$row['source'] = "YouTube";
				
		} elseif($row['source'] == "LOVEFiLM.com Updates"){

			$match = preg_match("#(Played|Watched|Has been sent) (.*?): (http://LOVEFiLM.com/r/\S*)#", $row['originaltext'], $matches);

			if($match){
			$row['content'] = sprintf('%s <a href="%s">%s</a>', $matches[1], $matches[3], $matches[2]);
			}

			$icon = IMAGE_ROOT.'other/favicon.png';
			$row['source'] = "LOVEFiLM";
		} elseif (
		            strtolower($row['source']) == "foursquare" 
		            or strtolower($row['source']) == "foursquare-mayor"
		          ){
		  if ($row['source'] == "Foursquare-Mayor"){
		    $icon = IMAGE_ROOT.'foursquare%20icons/mayorCrown.png';
		  } else {
			  $icon = IMAGE_ROOT.'foursquare%20icons/foursquare%20256x256.png';
		  }
		  
			$row['content'] = preg_replace("/#\w*/", "", $row['originaltext']);


			#preg_match("#(http://\S*)#", $row['content'], $matches);

			#echo $row['originaltext']."<br/>";
			
			$imat = preg_match("#I'm at (.*?) \((.*?)\)\. (http://\S*)#", $row['originaltext'], $matches);


			if ($imat){
				$row['content'] = sprintf('I\'m at <a href="%s">%s</a> (%s)', $matches[3], $matches[1], $matches[2]);
			} else {
				$row['content'] = twitterFormat($row['content']);
			}
			
			if (isset($matches[1])){
			$row['url'] = $matches[1];
			}
			#$row['content'] = preg_replace("#http://\S*#", "", $row['content']);
			
			#$row['content'] = twitterFormat($row['content']);
			
			#$row['url'] = "http://www.champions-online.com/character_profiles/user_characters/Jascain";
		} elseif ($row['source'] == "Kindle"){
			$icon = IMAGE_ROOT.'silk/book_open.png';


		} elseif ($row['source'] == "Miso"){
			$icon = IMAGE_ROOT.'silk/television.png';
			preg_match("#(http://\S*)#", $row['originaltext'], $matches);
			$row['url'] = $matches[1];
			$row['content'] = preg_replace("# http://\S*#", "", $row['originaltext']);


		} elseif($row['source'] == "Untappd"){
			$icon = IMAGE_ROOT.'other/beer.png';
			$row['small_icon'] = IMAGE_ROOT.'silk/drink.png';

			preg_match("#(http://\S*)#", $row['originaltext'], $matches);
			$row['url'] = $matches[1];
			$row['content'] = preg_replace("# http://\S*#", "", $row['originaltext']);

		}
		break;


	  


	case "twitter":
		$icon = IMAGE_ROOT.'twitter/Twitter-64.png';
		$row['small_icon'] = IMAGE_ROOT.'twitter/rounded-plain-16x16/twitter-02.png';

		switch ($row['source']){

			case "Steepster":
				$icon = IMAGE_ROOT.'silk/cup.png';
				$row['content'] = preg_replace("/#\w*/", "", $row['originaltext']);
				preg_match("#(http://\S*)#", $row['content'], $matches);
				$row['url'] = $matches[1];
				$row['content'] = preg_replace("#: http://\S*#", "", $row['content']);
				break;

			case "Goodreads":
				$icon = IMAGE_ROOT.'silk/book_open.png';
				preg_match("#(http://\S*)#", $row['originaltext'], $matches);
				$row['url'] = $matches[1];
				$row['content'] = preg_replace("# http://\S*#", "", $row['originaltext']);
				break;

			default:
				$row['source'] = "Twitter";

		}

		break; 

	case "flickr":
		$icon = IMAGE_ROOT.'silk/picture.png';
		$row['content'] = sprintf('<a href="%s">%s</a>', $row['url'], $row['content']);
		break;

  case "code":
    $icon = IMAGE_ROOT.'silk/application_osx_terminal.png';
    $row['content'] = $row['content'];
    break;
  
  case "oyster":
    $icon = IMAGE_ROOT.'tfl.png';
    break;

  case "tumblr":
	$icon = IMAGE_ROOT.'tumblr/tumblr_16.png';
	$row['small_image'] = IMAGE_ROOT.'tumblr/tumblr_16.png';
	break;

  default:
		$icon = IMAGE_ROOT.'silk/asterisk_orange.png';

	}

	if($row['image']){
		$icon = $row['image'];
			
		if(!isset($row['small_icon'])){
			$row['small_icon'] = $icon;
		}
	}


	$row['icon'] = $icon;
	$row['nicetime'] = nicetime($row['epoch']);

	#$row['content'] = $row['type'].$row['content'];

	$row['id'] = md5($row['systemid']);


  return $row;

  
}



function twitterFormat($text){
	

	$text = nl2br(ereg_replace("[[:alpha:]]+://[^<>[:space:]]+[[:alnum:]/]","<a href=\"\\0\">\\0</a>", $text));
	$text = preg_replace("#@(\w*)?#","<a href=\"http://www.twitter.com/\\1\">@\\1</a>", $text);
	
	$text = preg_replace("/#(\w*)/", "<a href=\"http://twitter.com/#search?q=%23\\1\">#\\1</a>", $text);
	
	$text = preg_replace("#^Aquarion: #", "", $text);

	$text = preg_replace("#http://raptr.com/\w*#", "", $text);
	$text = preg_replace("#^Xbox Live: #", "", $text);
	$text = preg_replace("# \(Xbox Live Nation\)$#", "", $text);
	
	return $text;
	
}


function getDatabase(){
  $config = parse_ini_file("../dbconfig.ini", true);
  $dbcxn = mysql_connect($config['database']['hostname'], $config['database']['username'], $config['database']['password']);
  mysql_select_db($config['database']['database'], $dbcxn);
  mysql_query("SET NAMES 'utf8' COLLATE 'utf8_unicode_ci'");
  return $dbcxn;
}


function lifestream_config($area, $item){
  $config = parse_ini_file("../dbconfig.ini", true);
  return $config[$area][$item];
}

