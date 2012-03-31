<html>
<head>
<title>Nicholas Avenell - Web Developer</title>

<link rel="stylesheet" href="/assets/css/style.css"/> 

<!--[if IE]><script language="javascript" type="text/javascript" src="/assets/js/jqplot/src/excanvas.js"></script><![endif]-->
<script type="text/javascript" src="/assets/js/jqplot/src/jquery-1.5.1.min.js"></script>
<script type="text/javascript" src="/assets/js/jqplot/src/jquery.jqplot.js"></script>
<script type="text/javascript" src="/assets/js/tickytacky.js"></script>
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

var music_data = [
<?PHP foreach($music as $artist => $count){
    printf("\t['%s', %d],\n", addslashes($artist), $count);
  }?>]
  

addMusicChart = function(){

		console.log("Hello Music Chart");
	if($('#musicChart')){
	
	
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
	
}
init = function(){

	$('#musicChart').addClass(chartClass);
	$('.contentbox').hide()
  
	  
}

load = function(){
	TickyTacky.rearrange(addMusicChart);
	$(window).resize(TickyTacky.rearrange);
}

$(document).ready(init);
$(window).load(load);

$(document).load(TickyTacky.rearrange)

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
<!--p>Bespoke Typing.</p> -->
<nav>[ <a href="http://hol.istic.net/Aquarion">About Me</a> | <a href="http://www.github.com/aquarion">Code</a> | <a href="http://www.linkedin.com/in/webperson">Employers</a> | <a href="http://www.aquarionics.com">Weblog</a> | <a href="http://hol.istic.net/Walrus">All my accounts everywhere</a> ]</nav>
</header>
<div id="datenav">
  <h2><a href="<?PHP echo $backwards ?>" title="<?PHP echo $backwards_title ?>">&#xff1c;</a>
  <?PHP 

  if($up){
	?><a href="<?PHP echo $up ?>"   title="<?PHP echo $up_title ?>">&#x2227;</a><?PHP
  }

  echo $datetitle;

  if(!$noforwards){?>
  <a href="<?PHP echo $onwards ?>"   title="<?PHP echo $onwards_title ?>">&#xff1e;</a>
  <?PHP } 

  if(!$today){?>
   <a href="/"   title="Today">&#x226b;</a>
  <?PHP } ?>
  
</h2>
<?PHP 
for($i=2000; $i <= date("Y"); $i++){
	$link = str_replace("[YEAR]", $i, $annuallink);
	print "| <a href=\"".$link."\">".$i."</a>";
}

?> |

</div>

<div id="tiles">

<ul id="tilelist" style="position: absolute;">
  
<?PHP 

$order = array();
foreach($structure as $classname => $items){
  $order[$classname] = count($items);
}

  
foreach($order as $classname => $count){
  
  $items = $structure[$classname];
  
  usort($items, "epochsort");
  
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


<?PHP if($from > time()){

  print '<li id="singleitem" class="contentbox">
    <a href="http://xkcd.com/338/"><img src="http://imgs.xkcd.com/comics/future.png" /></a><br/>
    <p>The future is a different country.<br/>
    We will do (willan on-do) thinks differently (willen differentian) there.</p>
  </li>'; 
  
}?>

<?PHP if($today){ ?>
<li id="Currently" class="contentbox content">
<iframe src="http://www.google.co.uk/latitude/apps/badge/api?user=-5055593116820320694&amp;type=iframe&amp;maptype=hybrid" width="180" height="300" frameborder="0"></iframe>
<?PHP } ?>


<?PHP if(count($music) && true){?>
  <li id="musicChart" class="contentbox Music chart"></li>
<?PHP } ?>

<li id="smallprint" class="contentbox content">Data for this is generated by <a href="https://github.com/aquarion/lifestream">Lifestream</a>, which is open source. No. There isn't an RSS feed.<br/>
This is an <a href="http://www.aquarionics.com">Aquarionic</a> production by <a href="http://istic.net">Istic Networks</a> </br>
All original content &copy; Nicholas Avenell 2000 to <?PHP echo date("Y") ?>, reposts, quotations and most tumblr content remain the property of whoever created it (Click though to the originals for the best citations I could find)

</li>

</ul>
  </div>

</div>
<br style="clear: both;"/>
</div>


</body>
</html>
