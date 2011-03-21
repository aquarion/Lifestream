<?PHP
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
  
	$text = $row['title'];
	$row['originaltext'] = $row['title'];

	
	$row['content'] = twitterFormat($text);
	
	if(!$row['source']){
		$row['source'] = $row['type'];
	}

	switch ($row['type']) {
		
	case "lastfm":
		$icon = "http://imperial.istic.net/static/icons/silk/music.png";
		break;
		
	case "gaming":
		$icon = "http://imperial.istic.net/static/icons/silk/joystick.png";
		if ($row['source'] == "Champions Online"){
			$icon = "http://imperial.istic.net/static/icons/games/ChampionsOnline.png";
			$row['url'] = "http://www.champions-online.com/character_profiles/user_characters/Jascain";
		} elseif ($row['source'] == "HeroStats"){

			$icon = "http://imperial.istic.net/static/icons/games/cityofheroes.png";
			$row['url'] = "http://cit.cohtitan.com/profile/13610";

		} elseif ($row['source'] == "Raptr" && preg_match('#Champions Online! #', $text)){
			$row['content'] .= "#";
		} elseif ($row['source'] == "XLN Live Integration"){
			$icon = "http://imperial.istic.net/static/icons/silk/controller.png";
			$row['url'] = "http://live.xbox.com/en-GB/profile/profile.aspx?pp=0&GamerTag=Jascain";
		} elseif (preg_match('#\#wow#', $text)){
			$row['source'] = "World of Warcraft";
			$icon = "http://imperial.istic.net/static/icons/games/world_of_warcraft.png";

		}
		break;

	case "steam":
		$icon = "http://imperial.istic.net/static/icons/games/steam.png";
		#$row['url'] = "http://steamcommunity.com/id/aquarion/";
		$row['title'] = "Achieved: ".$row['title'];
		break;

	case "apps":
	
		if(preg_match("#^I\S* \w* a YouTube video#", $row['content'])){
			$icon = "http://imperial.istic.net/static/icons/silk/film_add.png";
			$row['image'] = $icon;
			$match = preg_match("#I\S* \w* a YouTube video -- (.*?) (http.*)#", $row['originaltext'], $matches);
			
			$row['content'] = sprintf('<a href="%s">%s</a>', $matches[2], $matches[1]);
			$row['source'] = "YouTube";
				
		} elseif($row['source'] == "LOVEFiLM.com Updates"){

			$match = preg_match("#(Played|Watched|Has been sent) (.*?): (http://LOVEFiLM.com/r/\S*)#", $row['originaltext'], $matches);

			if($match){
			$row['content'] = sprintf('%s <a href="%s">%s</a>', $matches[1], $matches[3], $matches[2]);
			}

			$icon = "http://imperial.istic.net/static/icons/other/favicon.png";
			$row['source'] = "LOVEFiLM";
		} elseif ($row['source'] == "foursquare"){
			$icon = "http://imperial.istic.net/static/icons/silk/map_magnify.png";
			$row['content'] = preg_replace("/#\w*/", "", $row['originaltext']);


			#preg_match("#(http://\S*)#", $row['content'], $matches);

			#echo $row['originaltext']."<br/>";
			
			$imat = preg_match("#I'm at (.*?) \((.*?)\)\. (http://\S*)#", $row['originaltext'], $matches);


			if ($imat){
				$row['content'] = sprintf('I\'m at <a href="%s">%s</a> (%s)', $matches[3], $matches[1], $matches[2]);
			} else {
				$row['content'] = twitterFormat($row['content']);
			}
			
			$row['url'] = $matches[1];
			
			#$row['content'] = preg_replace("#http://\S*#", "", $row['content']);
			
			#$row['content'] = twitterFormat($row['content']);
			
			#$row['url'] = "http://www.champions-online.com/character_profiles/user_characters/Jascain";
		} elseif ($row['source'] == "Kindle"){
			$icon = "http://imperial.istic.net/static/icons/silk/book_open.png";
		} elseif ($row['source'] == "Miso"){
			$icon = "http://imperial.istic.net/static/icons/silk/television.png";
		}
		break;
	
	case "twitter":
		$icon = "http://imperial.istic.net/static/icons/twitter/squared-shiny-16x16/twitter-02.png";
		if ($row['source'] == "Steepster"){
			$icon = "http://imperial.istic.net/static/icons/silk/cup.png";
			$row['content'] = preg_replace("/#\w*/", "", $row['originaltext']);
			preg_match("#(http://\S*)#", $row['content'], $matches);
			
			$row['url'] = $matches[1];
			
			$row['content'] = preg_replace("#: http://\S*#", "", $row['content']);
			
			#$row['url'] = "http://www.champions-online.com/character_profiles/user_characters/Jascain";
		} elseif ($row['source'] == "web"){
			$row['source'] = "Twitter";
		}
		break; 

	case "flickr":
		$icon = "http://imperial.istic.net/static/icons/silk/picture.png";
		$row['content'] = sprintf('<a href="%s">%s</a>', $row['url'], $row['content']);
		break;

  case "code":
    $icon = "http://imperial.istic.net/static/icons/silk/application_osx_terminal.png";
    $row['content'] = $row['source'].": ".$row['content'];
    break;
    
    
	default:
		$icon = "http://imperial.istic.net/static/icons/silk/asterisk_orange.png";

	}

	if($row['image']){
		$icon = $row['image'];
	} 

	$row['icon'] = $icon;
	$row['nicetime'] = nicetime($row['epoch']);

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
  return $dbcxn;
}

