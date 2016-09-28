function QueryStringToHash(query) {

  if (query == '') return null;

  var hash = {};

  var vars = query.split("&");

  for (var i = 0; i < vars.length; i++) {
    var pair = vars[i].split("=");
    var k = decodeURIComponent(pair[0]);
    var v = decodeURIComponent(pair[1]);

    // If it is the first entry with this name
    if (typeof hash[k] === "undefined") {

      if (k.substr(k.length-2) != '[]')  // not end with []. cannot use negative index as IE doesn't understand it
        hash[k] = v;
      else
        hash[k] = [v];

    // If subsequent entry with this name and not array
    } else if (typeof hash[k] === "string") {
      hash[k] = v;  // replace it

    // If subsequent entry with this name and is array
    } else {
      hash[k].push(v);
    }
  } 
  return hash;
};
