<?PHP

require("../web/library.php");

getDatabase();
ORM::configure('logging', true);
$query = ORM::for_table('lifestream');

$blocksize = 100;
$next = 30;
$max = false;
$append = "append";

$message = "";

if(isset($_POST['after'])){
	$query->where_gt("date_created", $_POST['after']);
	$append = "prepend";
}


$query->where_not_null("title");
$query->where_not_equal("source", "tumblr");

define("AN_HOUR", 60*60 );
define("A_DAY", 60*60*24 );
define("A_WEEK", 60*60*24*7 );
define("A_MONTH", 60*60*24*30 );
define("A_YEAR", 60*60*24*364 );

$split = explode("/", $_POST['path']);
array_shift($split);

$last = end($split);
reset($split);

if($last == ""){
	array_pop($split);
}

$ordered = false;

if ($_POST['path'] == "/"){
	$max = 200;
	#$append = "prepend";
	$query->order_by_desc("date_created");
	$message = "This is the last $max things various services have seen me do.";
	$ordered = true;
} elseif (count($split) == 1){
	$from = mktime(0,0,0, 1, 1, $split[0]);
	$to   = strtotime("+1 year", $from) -1;
	$query->where_gt("date_created", date("Y-m-d 00:00", $from));
	$query->where_lt("date_created", date("Y-m-d 00:00", $to));

	$message = sprintf("Year from %s to %s", date("Y-m-d", $from), date("Y-m-d", $to));

} elseif(count($split) == 2 && strpos($split[1], "wk") !== false){
	$week = substr($split[1], 2);

	list($from, $to) = get_start_and_end_date_from_week($week, $split[0]);

	$query->where_gt("date_created", date("Y-m-d 00:00", $from));
	$query->where_lt("date_created", date("Y-m-d 00:00", $to));

	$message = sprintf("Week $week from %s to %s", date("Y-m-d", $from), date("Y-m-d", $to));

} elseif(count($split) == 2 && is_numeric($split[1])){
	$from = mktime (0, 0, 0, intval($split[1]), 1, intval($split[0]));
	$to   = mktime (0, 0, 0, intval($split[1] + 1), 1, intval($split[0])) -1;
	$query->where_gt("date_created", date("Y-m-d 00:00", $from));
	$query->where_lt("date_created", date("Y-m-d 00:00", $to));
	$message = sprintf("Month from %s to %s", date("Y-m-d", $from), date("Y-m-d", $to));
} elseif(count($split) == 3 && is_numeric($split[1])){
	// mktime ($hour, $minute, $second, $month, $day, $year)
	$from = mktime (0, 0, 0, intval($split[1]), intval($split[2]), intval($split[0]));
	$query->where_gt("date_created", date("Y-m-d 03:00", $from));
	$query->where_lt("date_created", date("Y-m-d 03:00", $from + A_DAY));
	$message = sprintf("Day from %s to %s", date("Y-m-d 03:00", $from), date("Y-m-d 03:00", $from + A_DAY));
	//$message = print_r($split, 1);#sprintf("Month from %s to %s", date("Y-m-d 00:00", $from), date("Y-m-d 00:00", $to));
} else {
	var_dump($split);
	die("What?");
}

if(!$ordered){
	$query->order_by_asc("date_created");
}


$countQuery = clone $query;
$count = $countQuery->count();

$query->limit($blocksize);

if(isset($_POST['offset'])){
	$offset = intval($_POST['offset']);
	$query->offset($offset);
} else {
	$offset = 0;
}
$items = $query->find_array();

if ($count > ($offset + $blocksize)){
	$next_offset = $offset + $blocksize;
	$next = 2;

	$percent = ($next_offset/($max ? $max : $count))*100;
	$message .= sprintf(" (%d%% Loaded)", $percent);
} else {
	$next_offset = 0;
}

if ($max && $next_offset >= $max){
	$next_offset = 0;
}

$return = array(
		'status' => 200, 
		'next' => $next, 
		'offset' => $next_offset, 
		'max' => $count, 
		"direction" => $append, 
		"message" => $message,
		'items' => array()
	);

foreach($items as $row){
	$return['items'][] = $row;
}

#$return['items'] = array_reverse($return['items']);

header("Content-Type: text/json");
print json_encode($return);