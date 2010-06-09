<?PHP
/*
Plugin Name: Aquarion Lifestream
Plugin URI: /projects/raoss/lifestream
Description: Lifestream
Version: 0.1a
Author: aquarion
Author URI: 
*/ 


function widget_aqxslifestream($args) {
    extract($args);
?>
        <?php echo $before_widget; ?>
            <?php echo $before_title
                . $after_title; ?>
        
<div id="lifestream">
     <ul>
        <li><a href="/misc/lifestream/?filter=-lastfm&format=html" title="Everything" rel="-lastfm">
			<span><img src="http://imperial.istic.net/static/icons/silk/asterisk_orange.png"/></span>
		</a></li>
         <li><a href="/misc/lifestream/?filter=lastfm&format=html" title="lifestreamContent" rel="lastfm">
			<span><img src="http://imperial.istic.net/static/icons/silk/music.png"/></span>
		</a></li>
         <li><a href="/misc/lifestream/?filter=gaming/steam&format=html" title="lifestreamContent"  rel="gaming/steam">
			<span><img src="http://imperial.istic.net/static/icons/silk/joystick.png"/></span>
		</a></li>
        <li><a href="/misc/lifestream/?filter=twitter&format=html" title="lifestreamContent"  rel="twitter">
			<span><img src="http://imperial.istic.net/static/icons/twitter/squared-shiny-16x16/twitter-02.png"/></span>
		</a></li>
        <li><a href="/misc/lifestream/?filter=flickr&format=html" title="lifestreamContent"  rel="flickr">
			<span><img src="http://imperial.istic.net/static/icons/silk/camera.png"/></span>
		</a></li>
     </ul>
	 <div id="lifestreamContent">
		
	 </div>
</div>
        <?php echo $after_widget; ?>
<?php
}


register_sidebar_widget('Lifestream Widget', 'widget_aqxslifestream');

