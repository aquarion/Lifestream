<html>
<head>

<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css">

<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.1.0/jquery.min.js"> </script>
<script src="./deparam.js"> </script>
<script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js"> </script>

<meta name="viewport" content="width=device-width, initial-scale=1">

<style type="text/css">
#fragment {
	white-space: pre-wrap;
	word-wrap: break-word;
	width: 100%;
}
</style>

</head>
<body>

<div class="container">
<h1>Battlenet Authentication</h1>

<h2>Access Key:</h2>

<textarea class="well js-copytextarea" id="fragment"><?PHP echo $_GET['code'] ?></textarea>
<button class="js-textareacopybtn"><i class="glyphicon glyphicon-copy"> </i> Copy Access Code</button>
</div>

<script type="text/javascript">

$(document).ready(function(){
	console.log(window.location.hash);
	if(window.location.hash) {
			paramstring = window.location.hash.substring(1);
			console.log(paramstring);
			dict = QueryStringToHash(paramstring);
			console.log(dict);
			var fragment = $("#fragment").html(dict['access_token']);
		} else {
			console.log("No Fragment");
		}
	} 
);

var copyTextareaBtn = document.querySelector('.js-textareacopybtn');

copyTextareaBtn.addEventListener('click', function(event) {
  var copyTextarea = document.querySelector('.js-copytextarea');
  copyTextarea.select();

  try {
    var successful = document.execCommand('copy');
    var msg = successful ? 'successful' : 'unsuccessful';
    console.log('Copying text command was ' + msg);
  } catch (err) {
    console.log('Oops, unable to copy');
  }
});

</script>
