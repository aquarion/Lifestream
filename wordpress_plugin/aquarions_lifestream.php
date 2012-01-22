<?PHP
/*
Plugin Name: Aquarion Lifestream
Plugin URI: http://www.aquarionics.com/projects/raoss/lifestream
Description: Lifestream
Version: 0.1a
Author: aquarion
Author URI: http://www.aquarionics.com
*/ 


#wp_enqueue_script("jquery");
#wp_enqueue_script("aqxs_lifestream", "/misc/lifestream/lifestream.js", "jquery");



add_action("wp_head", "aqxslifestream_css");


function aqxslifestream_css(){

echo <<<EOW
<link rel="stylesheet" href="/misc/lifestream/lifestream.css"/>
<script src="http://ajax.googleapis.com/ajax/libs/jquery/1.3.2/jquery.min.js"></script>
<script src="http://ajax.googleapis.com/ajax/libs/jqueryui/1.7.2/jquery-ui.min.js"></script>

<script src="/misc/lifestream/lifestream.js"></script>


<script type="text/javascript">

$(document).ready(lifestream.init);

</script>


EOW;


}

function widget_aqxslifestream($args) {
    extract($args);
?>
<div id="lifestream">
     <ul>
        <li><a href="http://www.aquarionics.com/misc/lifestream/?filter=-lastfm/-tumblr&format=html" title="lifestreamContent" rel="-lastfm/-tumblr">
			<span><img src="http://cdn.aquarionics.com/assets/icons/silk/asterisk_orange.png"/></span>
		</a></li>
         <li><a href="http://www.aquarionics.com/misc/lifestream/?filter=lastfm&format=html" title="lifestreamContent" rel="lastfm">
			<span><img src="http://cdn.aquarionics.com/assets/icons/silk/music.png"/></span>
		</a></li>
         <li><a href="http://www.aquarionics.com/misc/lifestream/?filter=gaming/steam&format=html" title="lifestreamContent"  rel="gaming/steam">
			<span><img src="http://cdn.aquarionics.com/assets/icons/silk/joystick.png"/></span>
		</a></li>
        <li><a href="http://www.aquarionics.com/misc/lifestream/?filter=twitter&format=html" title="lifestreamContent"  rel="twitter">
			<span><img src="http://cdn.aquarionics.com/assets/icons/twitter/squared-shiny-16x16/twitter-02.png"/></span>
		</a></li>
        <li><a href="http://www.aquarionics.com/misc/lifestream/?filter=flickr&format=html" title="lifestreamContent"  rel="flickr">
			<span><img src="http://cdn.aquarionics.com/assets/icons/silk/camera.png"/></span>
		</a></li>
		
    <li>
      <a href="http://www.aquarionics.com/misc/lifestream/?filter=code&format=html" title="lifestreamContent" rel="code">
      <span><img src="http://cdn.aquarionics.com/assets/icons/silk/application_osx_terminal.png"/></span>
</a></li>
		
     </ul>
	 <div id="lifestreamContent">
		
	 </div>
</div>
        <?php echo $after_widget; ?>
<?php
}


wp_register_sidebar_widget("com.aquarionics.lifestream.widgit", 'Lifestream Widget', 'widget_aqxslifestream', null);

