
// google.load("visualization", "1", {packages:["corechart"]});

var packeryInstance = false;
var mostRecent      = 0;
var nextDate = new Date(0);

var NicAve = {

    lastfm : {},

    music_chart : true,

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
        return;
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

        height = Math.ceil( (total*.75) / 56) * 56;
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
            // item.height((56));
            item.width(200);

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

            if( item && Formatting[this['source']] ){
                item = Formatting[this['source']](this, item)
            }
            if( item && Formatting[this['type']] ){
                item = Formatting[this['type']](this, item)
            }
            if( item && Formatting[this['source']+'_'+this['type']] ){
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

        if(data.locations && data.locations.length && !$('#mapcanvas').length ){
            item = $('<div class="item"></div>');
            item.attr("id", 'mapcanvas')
            item.addClass('map')
            item.width(500)
            item.height(56*6)
            item.attr("resized", true);
            $(container).prepend( item );
            packeryInstance.prepended( item );
            NicAve.leaflet_map(data.locations);
        }

        NicAve.build_music_chart();

        $(".item").each(function(){
            item = $(this);
            if (item.attr('id') == 'mapcanvas'){
                // item.html(item.outerHeight()+'x'+item.outerWidth());
                // return;
            }
            // if(!item.hasClass("photo") && !item.hasClass("achivement")){

                h = Formatting.h();
                w = Formatting.w();

                height = $(item).outerHeight();
                width  = $(item).outerWidth();

                inner_height = $(item).height();
                inner_width  = $(item).width();

                margin_height = height - inner_height;
                margin_width  = width  - inner_width;

                if($("img", item).length){
                    imgheight = $("img", item).height();
                    imgwidth = $("img", item).width();
                    if(imgheight > height){
                        height = imgheight;
                    }
                    if(imgwidth > width){
                        width = imgwidth;
                    }
                }

                nearest50_h = Math.ceil( (inner_height) / h) * h;
                item.height(nearest50_h-margin_height);
                nearest50_w = Math.ceil( inner_width / w) * w;
                item.width(nearest50_w-margin_width);

                if (item.width()/item.height() < .7 && ! item.attr("resized")){
                    item.height(h*2);
                }
                //item.html(item.width()/item.height())
            // }
            // item.html(
            //     item.outerWidth()+'x'+item.outerHeight()
            //     +'<br/>'+(item.outerWidth()/100)+' x '+(item.outerHeight()/56)
            //     +'<br/>'+(nearest50_w)+' x '+(nearest50_h)
            //     +'<br/>'+(nearest50_w-margin_width)+' x '+(nearest50_w-margin_height)
            //     );
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
    },


    // Map stuff

    locations_to_latlngs : function(locations){

      list = []

      for(i=0;i < locations.length; i++){
        markerpos = new L.LatLng(locations[i]['lat'], locations[i]['long']);
        markerpos['count'] = 2
        list.push(markerpos)
      }

      return list
    },



    leaflet_map : function(locations){
      
      if (locations.length == 0){
        return;
      }

      // replace "toner" here with "terrain" or "watercolor"
      var map = new L.Map("mapcanvas", {
          center: new L.LatLng(locations[0]['lat'], locations[0]['long']),
          zoom: 12
      });

      // var watercolorMap = new L.StamenTileLayer("watercolor");
      // var tonerliteMap = new L.StamenTileLayer("toner-lite");
      // var tonerMap = new L.StamenTileLayer("toner");
      var mapBoxMap = new L.tileLayer("https://api.mapbox.com/styles/v1/mapbox/light-v9/tiles/256/{z}/{x}/{y}?access_token=pk.eyJ1IjoiYXF1YXJpb24iLCJhIjoiQzRoeUpwZyJ9.gIhABGtR7UMR-LZUJGRW0A")
     

      map.addLayer(mapBoxMap);
      // map.addLayer(tonerMap);

      // var layer = new L.StamenTileLayer("toner-lines");
      // map.addLayer(layer);

      var labelsLayer = new L.StamenTileLayer("toner-labels");


      latlngs = NicAve.locations_to_latlngs(locations)
      var bounds = new L.LatLngBounds(latlngs);
      map.fitBounds(bounds);


      try {
          var heatmap = new L.webGLHeatmap({ 
            size : 19,
            opacity : .7,
            units: 'px'
          });
      } catch(err) {
        console.warn(err)
      }

      heatmapData = []
      foursquareMarkers = []

      for(i=0;i < locations.length; i++){

        point = locations[i]

        if(point['lat'] == 0 && point['long'] == 0){
            continue;
        }

        markerpos = new L.LatLng(point['lat'], point['long']);
        weight = .7
        

        if (point['icon']){
            image = point['icon'];
              marker = new L.Marker(markerpos, {
                map:map,
                draggable:false,
                title: point['title'],
                icon: L.icon({
                      iconUrl: point['icon'].replace('_64.png', '_bg_32.png'),
                      iconSize: [16, 16],
                  })
              });
              foursquareMarkers.push(marker)
              weight = 2
        }


        //heatmapData.push({'lat': point['lat'], 'lon': point['long'], 'value': 0.4});
        heatmapData.push([point['lat'], point['long'], weight]);


      }


      foursquareLayer = new L.featureGroup(foursquareMarkers)
      map.addLayer(foursquareLayer);
      
      var overlays = {
          //"Marker": marker,
          "Roads": labelsLayer,
          "Foursquare": foursquareLayer
      };

      if(heatmap && heatmapData.length){
        heatmap.setData(heatmapData)
        map.addLayer(heatmap);
        overlays['Heatmap'] = heatmap
      }

      if (foursquareMarkers.length + heatmapData.length == 0){

        $('#mapcanvas').remove()
      }
       
      // var baseLayers = {
      //     "Terminal": mapBoxMap,
      //     //"Marker": marker,
      //     "Toner": tonerMap,
      //     "Watercolor": watercolorMap,
      //     "Toner Lite": tonerliteMap,
      // };
      // L.control.layers(baseLayers, overlays).addTo(map);

    },

}

$(document).ready(NicAve.init);
