
google.load("visualization", "1", {packages:["corechart"]});

var packeryInstance = false;
var mostRecent      = 0;
var nextDate = new Date(0);

var NicAve = {

	lastfm : {},

	music_chart : false,

	init : function(){
      	google.setOnLoadCallback(NicAve.loadTiles);
	},

	loadTiles : function(){

		var container = document.querySelector('#tiles');
		packeryInstance = new Packery( container, { 'gutter' : 0} );

		NicAve.fetchNext(0)
	},

	fetchNext : function(offset){
		var data = {'path': window.location.pathname}
		if(offset){
			data.offset = offset;
		}
		$.ajax({
		  type: "POST",
		  url: '/fetchNext.php',
		  data: data,
		  success:  NicAve.success,
		  error:  NicAve.error,
		  dataType: 'json'
		});
	},

	fetchUpdate : function(mostRecent){
		var data = { 'after': mostRecent, 'path': window.location.pathname}
		$.ajax({
		  type: "POST",
		  url: '/fetchNext.php',
		  data: data,
		  success:  NicAve.success,
		  error:  NicAve.error,
		  dataType: 'json'
		});
	},

	build_music_chart : function(){
		if(Object.keys(NicAve.lastfm).length == 0){
			return;
		}

		data = [];
		other = 0;
		others = []

		total = 0;

		for (artist in NicAve.lastfm){
			total += NicAve.lastfm[artist];
		}

		for (artist in NicAve.lastfm){
			value = NicAve.lastfm[artist];
			if (value < 5 ){
				other += value;
				others.push(artist)
			} else {
				datum = [artist, value]
				data.push(datum)
			}
		}


		if(other > 0){
			data.push(["Others", other]);
		}

        var options = {
          "title" : "Music",
          'chartArea': {'width': '90%', 'height': '90%'},
          'backgroundColor' : 'transparent'
        };

		var container = document.querySelector('#tiles');

		if(!NicAve.music_chart){
			chartBox = $('<div id="music_chart"/>');
			$(container).append( chartBox );
			packeryInstance.appended( chartBox );
		}

		var data = google.visualization.arrayToDataTable(data);
		NicAve.music_chart = new google.visualization.PieChart(document.getElementById('music_chart'));

		height = Math.ceil( (total*.75) / 50) * 50;
		width  = Math.ceil( (total) / 100) * 100
		maxwidth = $(container).width();

		if (height > (maxwidth*.75)) {
			height = maxwidth*.75;
		}
		if (width > (maxwidth)) {
			width = maxwidth;
		}

		if(width < 300){
			height = 300;
			width = 400;
		}

		$('#music_chart').height(height);
		$('#music_chart').width(width);

		if(!$('#music_others').length){
			chartBox = $('<div id="music_others"/>');
			chartBox.addClass("item");
			$(container).append( chartBox );
			packeryInstance.appended( chartBox );
		}
		if(others.length > 1){
			plus = others.pop();
			$('#music_others').html("'Others' includes "+others.join(", ")+" &amp; "+plus);
		}


		NicAve.music_chart.draw(data, options);

	},

	success : function(data, status, xhdr){
		var container = document.querySelector('#tiles');

		$('#message').html(data.message);

		$('title').text("Nicholas Avenell - Web Person - "+data.title);

		if (data.nav.back){
			$('#navleft').attr("href", data.nav.back);
			$('#navleft').removeClass("navDisabled");
		} else {
			$('#navleft').attr("href", '');
			$('#navleft').addClass("navDisabled");
		}

		if (data.nav.forward){
			$('#navright').attr("href", data.nav.forward);
			$('#navleft').removeClass("navDisabled");
		} else {
			$('#navright').attr("href", '');
			$('#navright').addClass("navDisabled");
		}

		if (data.nav.up){
			$('#navup').attr("href", data.nav.up);
			$('#navup').removeClass("navDisabled");
		} else {
			$('#navup').attr("href", '');
			$('#navup').addClass("navDisabled");
		}

		$(data.items).each(function(){
			var identifier = hex_md5("id"+this['type']+this['systemid']);

			if($('#'+identifier).length){
				return;
			}

			item = $('<a class="item"></a>');
			item.attr("id", identifier)
			item.addClass(this['source'].replace(/\s/g, "_"))
			item.addClass(this['type'].replace(/\s/g, "_"))
			item.addClass((this['source']+'_'+this['type']).replace(/\s/g," "));

			if(!this['title'] && !this['image']){
				return;
			}

			item.html(this['title'])

			item.data("object", this);

			item.click(function(){
				//console.log($(this).data("object"));
				//return false;
			})


			if(this.image && this.image != 0){
				img = $('<img/>');
				img.addClass("icon")
				img.attr('src', this.image);
				item.prepend(img);
			}
			if(this.url && this.url != 0){
				item.attr("href", this.url);
			}

			if( Formatting[this['source']] ){
				item = Formatting[this['source']](this, item)
			}
			if( Formatting[this['type']] ){
				item = Formatting[this['type']](this, item)
			}
			if( Formatting[this['source']+'_'+this['type']] ){
				item = Formatting[this['source']+'_'+this['type']](this, item)
			}

			if(!item){
				return;
			}

			cite = $("<cite/>")
			cite.html(this['source']+"@"+this['date_created']);
			item.append(cite);


			if (data.direction == "append"){
				$(container).append( item );
				packeryInstance.appended( item );
			} else {
				$(container).prepend( item );
				packeryInstance.prepended( item );
			}


			if(this['epoch'] > mostRecent){
				mostRecent = this['epoch'];
			}
			updated = new Date(this['date_updated'])
			if (updated > nextDate){
				nextDate = updated;
			}
		})

		NicAve.build_music_chart();

		$(".item").each(function(){
			item = $(this);
			if(!item.hasClass("photo") && !item.hasClass("achivement")){
				height = $(item).height()+12;
				if($("img", item).length){
					imgheight = $("img", item).height();
					if(imgheight > height){
						height = imgheight;
					}
				}
				nearest50 = Math.ceil( height / 50) * 50;
				item.height(nearest50-12);
			}
		});
		packeryInstance.layout();

		if (data.offset){
			setTimeout(function(){NicAve.fetchNext(data.offset)}, data.next * 1000);
		} else {
			setTimeout(function(){NicAve.fetchUpdate(nextDate.toISOString())}, data.next * 1000);
		}
	},

	error : function(header, status, error){
		console.log(status);
		console.log(error);
	}
}

$(document).ready(NicAve.init);
