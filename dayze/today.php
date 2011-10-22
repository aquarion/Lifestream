<?PHP
require("../web/library.php");
header('Content-type: text/html; charset=UTF-8') ;
mb_language('uni');
mb_internal_encoding('UTF-8');

$dbcxn = getDatabase();

$dateformat = "l j<\s\u\p>S</\s\u\p> F Y";
$dateformat_txt = "l jS F Y";

define("A_DAY", 60*60*24 );
define("A_MONTH", 60*60*24*30 );
define("A_YEAR", 60*60*24*364 );

$today = false;

if (isset($_GET['year']) && isset($_GET['month']) && isset($_GET['day'])){
  $y = intval($_GET['year']);
  $m = intval($_GET['month']);  
  $d = intval($_GET['day']);  
  
  $from = mktime(0,0,0,$m,$d,$y);
  $to = mktime(23,59,59,$m,$d,$y);
  
  $datetitle = date($dateformat, $from);
  
  $backwards       = "/".date("Y", $from-A_DAY)."/".date("m", $from-A_DAY)."/".date("d", $from-A_DAY);
  $onwards         = "/".date("Y", $from+A_DAY)."/".date("m", $from+A_DAY)."/".date("d", $from+A_DAY);
  $onwards_title   = date($dateformat_txt, $from+A_DAY);
  $backwards_title = date($dateformat_txt, $from-A_DAY);
  
    
  $noforwards = false;
  if ($to > time()){
    $noforwards = true;
  }
  
  if(date("Y-m-d", $from) == date("Y-m-d")){
    $today = true;
  }

  $annualink = "/[YEAR]/".date("m", $from)."/".date("d", $from);  

} elseif (isset($_GET['year']) && isset($_GET['month'])){
  $y = intval($_GET['year']);
  $m = intval($_GET['month']);  
  $from = mktime(0,0,0,$m,1,$y);
  $to = mktime(23,59,59,$m,date("t", $from),$y);
  
  $next = mktime(0,0,0,$m+1,1,$y);
  $prev = mktime(0,0,0,$m-1,1,$y);
  
  $backwards       = "/".date("Y", $prev)."/".date("m", $prev);
  $onwards         = "/".date("Y", $next)."/".date("m", $next);
  $onwards_title   = date("F Y", $next);
  $backwards_title = date("F Y", $prev);
  
  $dateformat = "F Y";
  
  
  $noforwards = false;
  
  if (date("Ym", $next) > date("Ym")){
    $noforwards = true;
  }
  
  $datetitle = date($dateformat, $from);
  $annualink = "/[YEAR]/".date("m", $from);
  
} elseif (isset($_GET['year'])){
  $y = intval($_GET['year']);
  
  $from = mktime(0,0,0,1,1,$y);
  $to = mktime(23,59,59,12,31,$y);
  
  $next = mktime(0,0,0,1,1,$y+1);
  $prev = mktime(0,0,0,11,1,$y-1);
  
  $backwards       = "/".date("Y", $prev);
  $onwards         = "/".date("Y", $next);
  
  $onwards_title   = date("Y", $next);
  $backwards_title = date("Y", $prev);
  
  #$datetitle = date($dateformat, $from)." to ".date($dateformat, $to);
  
  $dateformat = "Y";
  $datetitle = date($dateformat, $from);
  
  $annuallink="/[YEAR]/";
    
  $noforwards = false;
  if (date("Y", $next) > date("Y")){
    $noforwards = true;
  }

  
} else {
  $from = mktime(0,0);
  $to = mktime(23,59,59);
  
  $datetitle = date($dateformat, $from);
  
  $backwards   = "/".date("Y", $from-A_DAY)."/".date("m", $from-A_DAY)."/".date("d", $from-A_DAY);
  $onwards     = "/".date("Y", $from+A_DAY)."/".date("m", $from+A_DAY)."/".date("d", $from+A_DAY);
  
  $onwards_title = date($dateformat_txt, $from+A_DAY);
  $backwards_title = date($dateformat_txt, $from-A_DAY);
  
  $today = $noforwards = true;
  $annualink = "/[YEAR]/".date("m", $from)."/".date("d", $from);  
}


$q = sprintf("select *, unix_timestamp(date_created) as epoch from lifestream where date_created between '%s' and '%s' order by date_created", date(DATE_ISO8601, $from), date(DATE_ISO8601, $to));

$results = mysql_query($q) or die(mysql_error());

$structure = array();

$structure['things'] = array();

$music = array();

while ($row = mysql_fetch_assoc($results)){
  
  $class = "Other";
  $row = process_lifestream_item($row);
  
  $id = md5($row['title']);
  
  switch ($row['type']){
    case "gaming":
    case "steam":
      $class = "Games";
      break;
      
    case "lastfm":
      $class = "Music";
      
      list($artist, $track) = explode(" – ", $row['title']);
      $id = md5($artist);
      if(strlen($artist) > 31){
        $artist = substr($artist, 0, 31);
      }
      
      if (!isset($music[$artist])){
        $music[$artist] = 1;
      } else {
        $music[$artist] += 1;
      }
      continue 2;
      break;
      
    case "code":
      $class = "Code";
      break;
      
    case "twitter":
      $class = "Twitter";
      break;
      
    case "tumblr":
      $class = "Tumblr";
      $row['content'] = $row['title'];
      break;
      
    case "location":
    case "oyster":
      $class = "Location";
      $id = md5($row['title']+$row['epoch']);
      break;
    
  }
  
  if ($row['source'] == "foursquare"){
    $class= "Location";
  }
  
  $row['class'] = $class;
  
  $class = "things";
  
  if (!isset($structure[$class])){
    $structure[$class] = array();
  }
  
  if (isset($structure[$class][$id])){
      if (!isset($structure[$class][$id]['subitems'])){
       $structure[$class][$id]['subitems'] = array();
      }
      $structure[$class][$id]['subitems'][] = $row['title'];
  } else {  
    $structure[$class][$id] = $row;
  }
}


$q = sprintf("select post_title, ID, unix_timestamp(post_date) as epoch from aqcom_wp_posts where post_status = 'publish' and post_date between '%s' and '%s' order by post_date", date(DATE_ISO8601, $from), date(DATE_ISO8601, $to));


$results = mysql_query($q) or die(mysql_error());

while ($row = mysql_fetch_assoc($results)){
  
  $class = "Blog";
  
  $row['content'] = $row['post_title'];
  $row['title'] = $row['post_title'];
  $row['url'] = "http://www.aquarionics.com/?p=".$row['ID'];
  $row['source'] = "Aquarionics";
  $row['icon'] = '';
  
  if (!isset($structure[$class])){
    $structure[$class] = array();
  }
  
  
  
  $row['class'] = $class;
  
  $class = "things";
  
  
  
  
  $structure[$class][md5($row['title'])] = $row;
  
}

?>
<html>


<head>
<title>Nicholas Avenell - Web Developer</title>

<link rel="stylesheet" href="/assets/css/style.css"/> 

<!--[if IE]><script language="javascript" type="text/javascript" src="/assets/js/jqplot/src/excanvas.js"></script><![endif]-->
<script type="text/javascript" src="/assets/js/jqplot/src/jquery-1.5.1.min.js"></script>
<script type="text/javascript" src="/assets/js/jqplot/src/jquery.jqplot.js"></script>
<script type="text/javascript" src="/assets/js/jqplot/src/plugins/jqplot.pieRenderer.js"></script>
<link rel="stylesheet" type="text/css" href="/assets/js/jqplot/src/jquery.jqplot.css" />

<script type="text/javascript">

<?PHP
if(count($music) > 10){
  $chartClass = 'chart_massive';
} elseif(count($music) > 5){
  $chartClass = 'chart_normal';
} else {
  $chartClass = 'chart_small';
}

printf('var chartClass = "%s"', $chartClass);
?>

var Move =	{

  copy	:   function(e, target)	{
	    var eId      = $(e);
	    var copyE    = eId.cloneNode(true);
	    var cLength  = copyE.childNodes.length -1;
	    copyE.id     = e+'-copy';

	    for(var i = 0; cLength >= i;  i++)	{
	    if(copyE.childNodes[i].id) {
	    var cNode   = copyE.childNodes[i];
	    var firstId = cNode.id;
	    cNode.id    = firstId+'-copy'; }
	    }
	    $(target).append(copyE);
	    },
  element:  function(e, target, type)	{
	    var eId =  $(e);
	    if(type == 'move') {
	       $(target).append(eId);
	    }

	    else if(type == 'copy')	{
	       this.copy(e, target);
	    }
	    }
}


function rearrange(){

	b = 256;

	boxes = new Array()

	$('.contentbox').each(function(){
		t = $(this)

		if (t.height() % b){
			h = t.outerHeight();
			d = h - t.height();
			n = b*(Math.floor(h/b) +1);
			t.height(n-d);
		}
		boxes.push(t);
		
	});

	boxes.sort( function (a, b){
		ah = $(a).height();
		bh = $(b).height();

		if (ah == bh){
			return 0;
		} else if(ah > bh) {
			return -1;
		} else {
			return 1;
		}

	} );

	t  = $('#tiles');
	tl = $('#tilelist');


	for(k in boxes){
		$(boxes[k]).appendTo(t);
		$(boxes[k]).appendTo(tl);
	}


}

var music_data = [
<?PHP foreach($music as $artist => $count){
    printf("\t['%s', %d],\n", addslashes($artist), $count);
  }?>]

init = function(){
  
  $('#musicChart').addClass(chartClass);
  
  $.jqplot.config.enablePlugins = true;
  
  line1 = music_data;
  plot1 = $.jqplot('musicChart', [line1], {
  title: 'Music',
  seriesDefaults:{
    renderer:$.jqplot.PieRenderer,
    rendererOptions:{sliceMargin:0, fill:true, shadow:true}
  },
  legend:{show:true},
  
  grid: { drawBorder: false, shadow: false },
  
  cursor: {
    showTooltip: true
  }

});



}

load = function(){
 rearrange();
}

$(document).ready(init);
$(window).load(load);

</script>

<style type="text/css">
<?PHP

$fn = date("Y/m/d", $from).".jpg";
$mn = date("Y/m", $from).".jpg";
$yn = date("Y", $from).".jpg";

if (file_exists("/var/www/hosts/dailyphoto.aquarionics.com/htdocs/".$fn) ) {
  ?>
  body {
    background-image: url("http://dailyphoto.aquarionics.com/<?PHP echo $fn; ?>");
  }
  <?PHP
} elseif (file_exists("/var/www/hosts/dailyphoto.aquarionics.com/htdocs/".$mn) ) {
  ?>
  body {
    background-image: url("http://dailyphoto.aquarionics.com/<?PHP echo $mn; ?>");
  }
  <?PHP
} elseif (file_exists("/var/www/hosts/dailyphoto.aquarionics.com/htdocs/".$yn) ) {
  ?>
  body {
    background-image: url("http://dailyphoto.aquarionics.com/<?PHP echo $yn; ?>");
  }
  <?PHP
}//endif
?>
</style>

</head>
<body>

<header>
<h1 id="header">Nicholas Avenell</h1>
<p>Bespoke Typing.</p>
<nav>[ <a href="http://hol.istic.net/Aquarion">Who?</a> | <a href="http://www.github.com/aquarion">Works</a> | <a href="http://www.linkedin.com/in/webperson">Worker</a> | <a href="http://www.aquarionics.com">Weblog</a> | <a href="http://hol.istic.net/Walrus">Walrus</a> ]</nav>
</header>
<div id="datenav">
  <h2><a href="<?PHP echo $backwards ?>" title="<?PHP echo $backwards_title ?>">&#xff1c;</a>
  <?PHP echo $datetitle ?>
  <?PHP if(!$noforwards){?>
  <a href="<?PHP echo $onwards ?>"   title="<?PHP echo $onwards_title ?>">&#xff1e;</a>
  <?PHP } ?>
  <?PHP if(!$today){?>
   <a href="/"   title="Today">&#x226b;</a>
  <?PHP } ?>
  
</h2>
<?PHP 
for($i=2000; $i <= date("Y"); $i++){
	$link = str_replace("[YEAR]", $i, $annualink);
	print "| <a href=\"".$link."\">".$i."</a>";
}

?> |

</div>
<br clear="both"/>

<div id="tiles" >

<ul id="tilelist">
  
<?PHP 

$order = array();
foreach($structure as $classname => $items){
  $order[$classname] = count($items);
}

  
foreach($order as $classname => $count){
  
  $items = $structure[$classname];
  
  
  foreach($items as $row){
    echo "<li class=\"contentbox ".$row['class']."\" >";
    
    if ($row['icon']){
      echo "<a href=\"".$row['url']."\" >";
      echo "<img src='".$row['icon']."' class=\"icon\"/>";
      echo "</a>";
    }
    
    $content = $row['content'];
    
    if (isset($row['subitems'])){
      $content .= " (+ ".count($row['subitems'])." more)";
    }
    
    echo $content;
        
    echo "<br/>";
    
    
    echo "<span class=\"cite\">".date("d/M/Y H:i", $row['epoch'])." &mdash; ";
    echo "<a href=\"".$row['url']."\" >".$row['source']."</a></span>";
    echo "</li>\n";
  }
  
}

?>


<?PHP if($today){ ?>

<li id="Currently" class="contentbox content">
  <h1>Currently</h1>

<!-- Google Public Location Badge -->
<!-- Google Public Location Badge -->
<iframe src="http://www.google.co.uk/latitude/apps/badge/api?user=-5055593116820320694&amp;type=iframe&amp;maptype=hybrid" width="180" height="300" frameborder="0"></iframe>
</div>
<?PHP } ?>

<?PHP if($from > time()){

  print '<div id="singleitem" class="contentbox">
    <a href="http://xkcd.com/338/"><img src="http://imgs.xkcd.com/comics/future.png" /></a><br/>
    <p>The future is a different country.<br/>
    We will do (willan on-do) thinks differently (willen differentian) there.</p>
  </div>'; 
  
}?>


<?PHP if(count($music) && false){?>
  <li id="musicChart" class="contentbox Music chart"></li>
<?PHP } ?>

</ul>
  </div>

</div>

<hr/>
<footer>Data for this is generated by <a href="https://github.com/aquarion/lifestream">Lifestream</a>, which is open source. No. There isn't an RSS feed.<br/>
This is an <a href="http://www.aquarionics.com">Aquarionic</a> production by <a href="http://istic.net">Istic Networks</a></footer>

</body>
</html>
