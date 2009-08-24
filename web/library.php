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
                $date .= " ".$plus;
        }

        #$date .= " (".$since.")";

        return $date;
}
