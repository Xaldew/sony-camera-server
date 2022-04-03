class Camera
{
    constructor()
    {
        this.server = {};
        this.guide = {};
        this.system = {};
        this.camera = {};
        this.avContent = {};

        this.status = null;
        this.find_methods();
        this.prettyfy = true;
    }

    find_methods()
    {
        var endpoints = [["guide", this.guide],
                         ["system", this.system],
                         ["camera", this.camera],
                         ["avContent", this.avContent]];
        let methDiv = document.getElementById("camera-methods");
        for (var i = 0; i < endpoints.length; i++)
        {
            let epName = endpoints[i][0];
            let epObj = endpoints[i][1];
            let epNode = document.createElement("div");
            epNode.id = epName;
            epNode.class = "camera-endpoint";
            epNode.innerHTML = "<h3>" + epName + "</h3>";
            methDiv.appendChild(epNode);

            var xhr = new XMLHttpRequest();
            xhr.open("POST", epName, false);
            xhr.setRequestHeader("Content-Type", "application/json");
            let params = {
                method: "getMethodTypes",
                params: [""],
            };
            xhr.send(JSON.stringify(params));
            if (xhr.status === 200)
            {
                let result = JSON.parse(xhr.responseText);
                let methods = result["results"];
                // We need to be able to create or save this data to
                // properly populate the interface.
                for (var j = 0; j < methods.length; j++)
                {
                    let name = methods[j][0];
                    let params = methods[j][1];
                    let responses = methods[j][2];
                    let version = methods[j][3];
                    let epName = endpoints[i][0];

                    // Create camera method.
                    let mNode = document.createElement("div");
                    mNode.id = name;
                    mNode.class = "camera-method";
                    mNode.endpoint = epName;
                    mNode.innerHTML = "<h4>" + name + "(v" + version + ")" + "</h4>";
                    mNode.innerHTML += "<button onclick=submitCameraMethod(this.parentNode)>Submit</button>";
                    epNode.appendChild(mNode);

                    // Create parameter toggles.
                    for (var k = 0; k < params.length; k++)
                    {
                        let pNode = createParameterNode(params[k]);
                        mNode.appendChild(pNode);
                    }

                    // Create a function for this method.
                    epObj[name] = function(params = {})
                    {
                        var req = new XMLHttpRequest();
                        req.open("POST", epName, false);
                        req.setRequestHeader("Content-Type", "application/json");
                        params["method"] = name;
                        req.send(JSON.stringify(params));
                        if (req.status === 200)
                        {
                            return JSON.parse(req.responseText);
                        }
                        else
                        {
                            return {};
                        }
                    }
                }
            }
        }
    }
}

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

    camera = new Camera();
    console.log(camera.system.getVersions());

    // var status = getStatus();
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
    area.scrollTop = area.scrollHeight;
}

function prettyLog(btn)
{
    camera.prettyfy = !camera.prettyfy;
    if (camera.prettyfy)
    {
        btn.innerHTML = "Pretty";
    }
    else
    {
        btn.innerHTML = "Terse";
    }
}

function clearLog()
{
    let area = document.getElementById("camera-logging-area");
    area.value = "";
}


function createParameterNode(params)
{
    let pNode = document.createElement("div");
    pNode.class = "camera-param";
    if (params === "bool")
    {
        pNode.innerHTML += "bool";
    }
    else if (params === "bool*")
    {
        pNode.innerHTML += "bool*";
    }
    else if (params === "int")
    {
        pNode.innerHTML += "int";
    }
    else if (params === "int*")
    {
        pNode.innerHTML += "int*";
    }
    else if (params === "double")
    {
        pNode.innerHTML += "double";
    }
    else if (params === "double*")
    {
        pNode.innerHTML += "double*";
    }
    else if (params == "string")
    {
        pNode.innerHTML += "string";
    }
    else if (params == "string*")
    {
        pNode.innerHTML += "string*";
    }
    else
    {
        let multiple = false;
        if (params.endsWith("*"))
        {
            multiple = true;
            params = params.slice(0, params.length - 1);
        }
        // JSON object types.
        let ents = JSON.parse(params);
        for (let [k, v] of Object.entries(ents))
        {
            pNode.innerHTML += k + " : " + v + "</br>";
        }
    }

    return pNode;
}


function submitCameraMethod(method)
{
    // Collect all parameters, then call the appropriate method.
    let ep = method.endpoint;
    let res = camera[ep][method.id]();
    log(method.id + ":");
    if (camera.prettyfy)
    {
        log(JSON.stringify(res, null, 4));
    }
    else
    {
        log(JSON.stringify(res));
    }
}
