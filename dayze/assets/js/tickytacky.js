
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


TickyTacky = {

	grid        : [[0,0,0],[0,0,0]],
	currentline : 0,
	b           : 200,
	width       : false,
	padding     : 10,

	getBestPosition : function (box){
		console.log(box);
		column = -1;
		if (TickyTacky.width == false){
			TickyTacky.width = box.outerWidth();
		}

		if (TickyTacky.currentline > 10){
			TickyTacky.currentline -= 10;
		}

		//TickyTacky.currentline = 0;

		columns = Math.round(box.outerWidth() / TickyTacky.width);
		height  = Math.round(box.height()     / TickyTacky.b);

		n = 0;

		while (column == -1){
			n = n + 1;
			if (n == 100){
				console.log("Giving up");
				return;
			}
			if (TickyTacky.grid[TickyTacky.currentline][0] == 0){
				column = 0;
			} else if (TickyTacky.grid[TickyTacky.currentline][1] == 0 && columns < 3){
				column = 1;
			} else if (TickyTacky.grid[TickyTacky.currentline][2] == 0 && columns < 2){
				column = 2;
			}
			if (column != -1){
				console.log("found a fit at R"+TickyTacky.currentline+"/C"+column);
				fit = true;
				for (i=column; i < columns; i++){
					if (TickyTacky.grid[TickyTacky.currentline][i] != 0){
						console.log("But R"+TickyTacky.currentline+"/C"+i+" is filled. Moving on...");
						fit = false;
					}
				}
				if (fit != true){
					column = -1;
				}
			}
			if ( column == -1){
				TickyTacky.currentline = TickyTacky.currentline+1;
				if (TickyTacky.grid.length <= TickyTacky.currentline) {
					TickyTacky.grid[TickyTacky.currentline] = [0,0,0]
				}
				
			}
		}


		left = column * (TickyTacky.width+TickyTacky.padding);
		

		top_offset = TickyTacky.currentline * (TickyTacky.b+TickyTacky.padding);

		//grid[currentline][column] = height;
		
		//if (height > 1){
			for (i=0;i<height;i++){
				while (TickyTacky.grid.length <= TickyTacky.currentline + i){
					TickyTacky.grid[TickyTacky.grid.length] = [0,0,0];
				}
				TickyTacky.grid[TickyTacky.currentline+i][column] = height;
				if (columns > 1){
					TickyTacky.grid[TickyTacky.currentline+i][column+1] = height;
				}
				if (columns > 2){
					TickyTacky.grid[TickyTacky.currentline+i][column+2] = height;
				}
			}
		//}
		
		return [top_offset, left];
	},

	rearrange : function(){

		boxes = new Array()

		$('.contentbox').each(function(){
			t = $(this)

			if (t.height() % TickyTacky.b){
				h = t.outerHeight();
				d = h - t.height();
				n = TickyTacky.b * (Math.floor(h/TickyTacky.b) +1);
				t.height(n-d);
			}
			boxes.push(t);
			
		});

		/*boxes.sort( function (a, b){
			ah = $(a).height();
			bh = $(b).height();

			if (ah == bh){
				return 0;
			} else if(ah > bh) {
				return -1;
			} else {
				return 1;
			}

		} ); */


		t  = $('#tiles');
		tl = $('#tilelist');

		for(k in boxes){
			//$(boxes[k]).appendTo(t);
			//$(boxes[k]).appendTo(tl);
			position = TickyTacky.getBestPosition($(boxes[k]))
			$(boxes[k]).css("top", position[0]);
			$(boxes[k]).css("left", position[1]);
			$(boxes[k]).css("position", "absolute");
			}


	}
}

