function init()
{
    // Enable file-tree toggling.
    var toggler = document.getElementsByClassName("caret");

    // Note: Loading type of this script, if there are no "caret" classes at
    // read-time, this won't work...
    for (var i = 0; i < toggler.length; i++) {
        toggler[i].addEventListener("click", function() {
            this.parentElement.querySelector(".nested").classList.toggle("active");
            this.classList.toggle("caret-down");
        });
    }

    var status = getStatus();

    getDevices();
}

function setLiveviewFocus(event, img)
{
    let x = 100 * (event.offsetX / img.width);
    let y = 100 * (event.offsetY / img.height);

    var xhr = new XMLHttpRequest();
    xhr.open("POST", "camera", true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    let value = {
        method: "setTouchAFPosition",
        params: [x, y],
    };
    xhr.onreadystatechange = function()
    {
        if (this.readyState === XMLHttpRequest.DONE && this.status === 200)
        {
            let result = JSON.parse(this.response);
            log(JSON.stringify(value) + ":");
            log("    " + JSON.stringify(result))
        }
    }
    xhr.send(JSON.stringify(value));
}

function getDevices()
{
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "server", true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onreadystatechange = function()
    {
        if (this.readyState === XMLHttpRequest.DONE && this.status === 200)
        {
            let devicesNode = document.getElementById("device-select");
            // Delete old list.
            while (devicesNode.firstChild) {
                devicesNode.removeChild(devicesNode.lastChild);
            }

            // Parse and insert new devices.
            let result = JSON.parse(this.response);
            let devices = result["result"];
            for (var i = 0; i < devices.length; i++)
            {
                let node = document.createElement("option");
                node.innerText = devices[i];
                devicesNode.appendChild(node);
            }
        }
    };
    xhr.send(JSON.stringify({
        method: "getDevices",
    }));
}

function refreshDevices()
{
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "server", true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({
        method: "refreshDevices",
    }));
    xhr.onreadystatechange = function()
    {
        if (this.readyState === XMLHttpRequest.DONE && this.status === 200)
        {
            let devicesNode = document.getElementById("device-select");
            // Delete old list.
            while (devicesNode.firstChild) {
                devicesNode.removeChild(devicesNode.lastChild);
            }

            // Parse and insert new devices.
            let result = JSON.parse(this.response);
            let devices = result["result"];
            for (var i = 0; i < devices.length; i++)
            {
                let node = document.createElement("option");
                node.innerText = devices[i];
                devicesNode.appendChild(node);
            }
        }
    };
}

function changeCameraMode(input)
{
    // let tst = document.querySelector('input[name="mode"]:checked');
    // console.log(input.value);
    console.log(input);
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "camera", true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    let value = {
        method: "setCameraFunction",
    };

    if (input.value === "shooting")
    {
        value.params = ["Remote Shooting"];
    }
    else if (input.value === "contents")
    {
        value.params = ["Contents Transfer"];
    }
    xhr.onreadystatechange = function()
    {
        if (this.readyState === XMLHttpRequest.DONE && this.status === 200)
        {
            let result = JSON.parse(this.response);
            log(JSON.stringify(value) + ":");
            log("    " + JSON.stringify(result));
            if (input.value == "contents" && result["result"][0] === 0)
            {
                updateFileTree();
            }
        }
    };
    xhr.send(JSON.stringify(value));
}

function addValue(input)
{
    // The 'input' is any of the input nodes in the parameter value, so remove
    // onfocus for all nodes in the parent to prevent this one from spawning
    // more children.
    let parent = input.parentNode;
    let clone = parent.cloneNode(true);
    // clone.id = "something-new";
    for (i = 0; i < parent.childNodes.length; i++)
    {
        console.log(parent.childNodes[i]);
        parent.childNodes[i].onfocus = null;
    }

    // Append the clone to the parent.
    parent.parentNode.appendChild(clone);
}


function updateFileTree()
{
    log("Starting rebuild of file-tree...");
    let tree = document.getElementById("filetree");

    let files = getFiles();
}

function getFiles()
{
    {
        var xhr = new XMLHttpRequest();
        xhr.open("POST", "avContent", false);
        xhr.setRequestHeader("Content-Type", "application/json");
        let params = {
            method: ""
        };
    }

    var xhr = new XMLHttpRequest();
    xhr.open("POST", "avContent", true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    let value = {
        method: "getCameraFunction",
    };
}


function getStatus()
{
    return "";
}


function log(msg)
{
    let area = document.getElementById("camera-logging-area");
    area.value += msg + "\n";
}
