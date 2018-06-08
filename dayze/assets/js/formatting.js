
var h = 80;
var w = h*1.77;

var Formatting = {

	'h' : function(){ return h },
	'w' : function(){ return w },

	'achivement' : function(object, element){

		if(element.hasClass("Raptr")){
			return element;
		}
		if(element.hasClass("blizzard_wow")){
			return element;
		}

		title = decodeEntities(object.title)
		fulldata = JSON.parse(object.fulldata_json)
		

		element.addClass("achivement");


		if ( title.search(" --- ") !== -1 ){
			delim = " --- "
		} else if ( title.search(" -- ") !== -1 ){
			delim = " -- "
		} else {
			delim = " – "
		}
		
		newhtml = "<div class=\"frame\" style=\"background-image: url('"+object.image+"')\">"
		newhtml += "<div class=\"achievement_top\">"+title.split(delim)[0]+"</div>"
		newhtml += "<div class=\"achievement_bottom\">"+title.split(delim)[1]+"</div>"
		newhtml += "</div>"


		element.html(newhtml);

		$('.frame', element).css('background-image', object.image)

		element.attr("title", (object.source+" "+object.type).capitalize()+": "+title)

		element.height(h*2);
		element.width(w*1);



		return element;
	},

	'destiny2_gaming' : function(object, element){

		if(element.hasClass("Raptr")){
			return element;
		}

		title = decodeEntities(object.title)
		fulldata = JSON.parse(object.fulldata_json)
		

		// element.css("background-image", "url('https://art.istic.net/iconography/games/destiny.png')");
		element.css("background-image", "url('https://www.bungie.net/" + fulldata.activity_info.pgcrImage + "')");
		element.css("background-size", "cover");
		element.addClass("achivement");


		delim = " --- "
		
		newhtml = "<div class=\"frame\">"
		newhtml += "<div class=\"achievement_top\">Destiny 2</div>"
		newhtml += "<div class=\"achievement_bottom\">"+title.split(delim)[0]+"</div>"
		newhtml += "</div>"


		element.html(newhtml);

		element.attr("title", (object.source+" "+object.type).capitalize()+": "+title)

		element.height(h*2);
		element.width(w*2 - 12);



		return element;
	},


	'blizzard_wow' : function(object, element){

		if(element.hasClass("Raptr")){
			return element;
		}

		title = decodeEntities(object.title)
		fulldata = JSON.parse(object.fulldata_json)
		

		element.addClass("achivement");


		delim = " --- "
		
		newhtml = "<div class=\"frame\" style=\"background-image: url('"+object.image+"')\">"
		// newhtml += "<div class=\"achievement_top\">Destiny 2</div>"
		newhtml += "<div class=\"achievement_bottom\">"+title.split(delim)[0]+"</div>"
		newhtml += "</div>"


		element.html(newhtml);

		$('.frame', element).css('background-image', object.image)

		element.attr("title", (object.source+" "+object.type).capitalize()+": "+title)

		element.height(h*2);
		element.width(w*2 - 12);



		return element;
	},


	'kickstarter' :  function(object, element){

                element.css("background-image", "url('"+object.image+"')");
                element.css("background-size", "contain");
                element.addClass("achivement");
                element.html("");

                element.attr("title", (object.source+" "+object.type).capitalize()+": "+decodeEntities(object.title))

                element.height(h*2);
                element.width(w*2-12);

                return element;
        },

	'facebook' : function(object, element){

		if(object['type'] == 'status'){
	        full_data = JSON.parse(object['fulldata_json'])
	        element.html(full_data['message'].replace(/\n/g, "<br />"))
	    }
		element.width(w*3-12);


		if(object.image && object.image != '0'){
	        element.css("background-image", "url('"+object.image+"')");
	        element.css("background-size", "cover");
	        element.css("background-position", "center center");
	        element.height(h*2)

			element.removeClass("photo");
			element.width(w*2-12);
	        full_data = JSON.parse(object['fulldata_json'])
	        if(full_data['message']){
	                element.html("<p>"+full_data['message'].replace(/\n/g, "<br />")+"</p>")
	        } else {
	        	element.html("")
	        }
		}

		//element.height(h*2);
		element.data("growthis", true);
		return element;
	},

	'oyster' : function(object, element){

		var journey = element.html();

		journey = journey.replace(/\[.*?\]/, '');
		element.addClass("centered");
		element.html(journey);
		return element;

	},

	'lastfm' : function(object, element){
		split = object.title.split(' \u2013 ');
		artist = split[0]

		if(NicAve.lastfm[artist]){
			NicAve.lastfm[artist] += 1;
		} else {
			NicAve.lastfm[artist] = 1;
		}
		return false
	},

	// 'facebook_photo' : function(object, element){
	// 	element.html(
	// 		'<p>' + object.title + '</p>'
	// 		// +'<img src="'+object.image+'" height="73"/>'
	// 		);

 //        element.css("background-image", "url('"+object.image+"')");
 //        element.css("background-size", "cover");
 //        element.css("background-position", "center center");
 //        element.height(h*3-12)

	// 	element.removeClass("photo");
	// 	element.data("growthis", true);
	// 	return element;
	// },

	'facebook_link' : function(object, element){
		fulldata = JSON.parse(object.fulldata_json)

		aqcom = /^https?:\/\//g
		if (aqcom.test(object.url)){
			return false;
		}

		element.html(
			'<p>' + object.title + '</p>'
			// +'<img src="'+object.image+'" height="73"/>'
			);
		element.removeClass("photo");
		element.data("growthis", true);
		element.css("width", w*2);
		element.css("height", h*3);
		return element;
	},

	// 'facebook_video' : function(object, element){
	// 	element.html(
	// 		'<p>' + object.title + '</p>'
	// 		+'<img src="'+object.image+'" height="73"/>'
	// 		);
	// 	element.removeClass("photo");
	// 	element.data("growthis", true);
	// 	return element;
	// },

	'tumblr_photo' : function(object, element){
		element.css("background-image", "url('"+object.image+"')");
		element.addClass("photo");
		element.html("")
		element.css("width", w*3);
		element.css("height", h*4);
		element.ready(Formatting.photoresize);
		return element;
	},

	'tumblr' : function(object, element){
		element.css("width", w*4);
		return element;
	},

	'tumblr_text' : function(object, element){
		element.css("width", w*4);
		// element.css("height", 3*h);
		fulldata = JSON.parse(object.fulldata_json)
		if(fulldata['reblog']){
			element.html('<div class="frame"><blockquote>'
				+ (fulldata['title'] ? '<h2>'+fulldata['title']+'</h2>' : '')
				+fulldata['summary']
				+'</blockquote>'
				+fulldata['reblog']['comment']+'</div>');
		}
		return element;
	},

	'tumblr_video' : function(object, element){
		element.css("width", w*4);
		// element.css("height", 3*h);
		fulldata = JSON.parse(object.fulldata_json)
		if(fulldata['reblog']){
			element.html('<div class="frame"><blockquote>'
				+fulldata['summary']
				+'</blockquote>'
				+fulldata['player'][1]['embed_code']
				+fulldata['reblog']['comment']
				+'</div>');
		}
		return element;
	},

	'flickr' : function(object, element){

		element.addClass("photo");
		element.css("background-image", "url('"+object.image+"')");
		element.ready(Formatting.photoresize);

		element.html("")

		return element;
	},

	'Raptr' : function(object, element){

		element.addClass("gaming");
		element.removeClass("twitter");
		
		return element;
	},

	'Foursquare-Badge' : function(object, element){

		element.addClass("achivement");
		element.css("background-image", "url('"+object.image+"')");
		element.css("width", 1*w);
		// element.css("height", 4*h);
		element.css("background-size", "cover");

		element.html("")

		return element;
	},

	'Foursquare' : function(object, element){
		element.height(h*1);
		element.width(w*.5);
		return element;
	},


	'fitbit' : function(object, element){
		element.html(element.html().replace("activeScore", "Active Score"));
		img = $('<img/>');
		img.addClass("icon")
		img.attr('src', "http://art.istic.net/iconography/fitbit.png");
		element.prepend(img);
		return element;
	},

	'twitter' : function(object, element){

		if(object.source == 'WordPress.com'){
			return false;
		}

		fulldata = JSON.parse(object.fulldata_json)

		element.css("height", 1*h);
		return element;
	},

	'aquarionics' : function(object, element){
		//element.height(200);
		element.height(h*4);
		element.width(w*4);

		if(object.image){
			element.css("background-image", "url('"+object.image+"')");
		} else {
			element.css("background", "rgba(0,0,0,.8)");
		}
		element.css("background-size", "cover");
		element.css("background-position", "center");
		element.html('<div class="bloginner">' + object.title + '</div><img src="http://art.istic.net/iconography/aqcom/logo_64.png" height="64" width="64" class="aqcomicon">');

		element.attr("title", (object.source+" "+object.type).capitalize()+": "+decodeEntities(object.title))


		return element;
	},


	photoresize : function(thing){
	}
};

Formatting.badge = Formatting.achivement;
Formatting.gaming = Formatting.achivement;
Formatting.rapr = false;
