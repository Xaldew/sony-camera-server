class Camera
{
    constructor()
    {
        this.server = {};
        this.status = null;
        this.prettyfy = true;
        this.endpoints = [];

        this.find_endpoints();
        this.find_methods();
    }

    find_endpoints()
    {
        var xhr = new XMLHttpRequest();
        xhr.open("POST", "server", false);
        xhr.setRequestHeader("Content-Type", "application/json");
        let params = {
            method: "getEndpoints",
        };
        xhr.send(JSON.stringify(params));
        if (xhr.status === 200)
        {
            let res = JSON.parse(xhr.responseText);
            this.endpoints = res["result"];
            console.log(this.endpoints);
        }
    }

    find_methods()
    {
        let methDiv = document.getElementById("camera-methods");
        for (let [epName, methods] of Object.entries(this.endpoints))
        {
            this[epName] = {};
            let epNode = document.createElement("div");
            epNode.id = epName;
            epNode.class = "camera-endpoint";
            epNode.innerHTML = "<h3>" + epName + "</h3>";
            methDiv.appendChild(epNode);

            // Populate the camera with function calls and the UI with the
            // toggles according to the spec.
            for (let [method, responses] of Object.entries(methods))
            {
                // Create a function for this method.
                this[epName][method] = function(args = [])
                {
                    var req = new XMLHttpRequest();
                    req.open("POST", epName, false);
                    req.setRequestHeader("Content-Type", "application/json");
                    var params = {method: method, params: args};
                    console.log(params);
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

                // Create camera method.
                let mNode = document.createElement("div");
                mNode.id = method;
                mNode.className = "camera-method";
                mNode.endpoint = epName;
                let title = document.createElement("h4");
                title.innerText = method;
                mNode.appendChild(title);
                epNode.appendChild(mNode);

                // Create parameter toggles.
                let args = responses["parameters"];
                mNode.expects = responses["expects"];
                for (let [name, spec] of Object.entries(args))
                {
                    let type = spec["type"];
                    let opts = spec["options"];
                    let pNode = createParameterNode(method, name, type, opts);
                    mNode.appendChild(pNode);
                }

                let submit = document.createElement("button");
                let lbl = document.createElement("label");
                submit.className = method + "-submit";
                submit.onclick = function() { submitCameraMethod(this.parentNode); };
                submit.innerText = "Submit";
                let arg_props = Object.getOwnPropertyNames(args);
                if (arg_props.length === 0)
                {
                    mNode.appendChild(document.createElement("br"));
                }
                mNode.appendChild(lbl);
                mNode.appendChild(submit);
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


function createParameterNode(method, name, type, opts)
{
    let pNode = document.createElement("div");
    pNode.className = "camera-param";
    pNode.id = name;
    let iNode = document.createElement("div");
    iNode.className = "parameter";
    pNode.appendChild(iNode);
    if (type.startsWith("bool"))
    {
        var toggle = document.createElement("input");
        toggle.type = "checkbox";
        toggle.id = name;
        toggle.name = name;
        toggle.value = name;
        toggle.value_type = "bool";

        var lbl = document.createElement("label");
        lbl.htmlFor = name;
        lbl.appendChild(document.createTextNode(name));
        // if (opts.length)
        // {
        //     toggle.checked = true;
        // }
        iNode.appendChild(lbl);
        iNode.appendChild(toggle);
    }
    else if (type.startsWith("int") ||
             type.startsWith("double"))
    {
        var toggle = document.createElement("input");
        toggle.type = "number";
        toggle.id = name;
        toggle.name = name;

        if (type.startsWith("int"))
        {
            toggle.value_type = "int";
        }
        else
        {
            toggle.value_type = "double";
        }

        var lbl = document.createElement("label");
        lbl.htmlFor = name;
        lbl.appendChild(document.createTextNode(name));

        if (opts.length > 0)
        {
            var datalist = document.createElement("datalist");
            datalist.id = method + "-" + name + "-data";
            for (const e of opts)
            {
                var o = document.createElement("option");
                o.value = e;
                datalist.appendChild(o);
            }
            pNode.appendChild(datalist);
            toggle.setAttribute("list", datalist.id);
            toggle.min = Math.min.apply(Math, opts);
            toggle.max = Math.max.apply(Math, opts);
        }
        iNode.appendChild(lbl);
        iNode.appendChild(toggle);
    }
    else if (type.startsWith("string"))
    {
        var toggle = document.createElement("input");
        toggle.type = "text";
        toggle.id = name;
        toggle.name = name;
        toggle.value_type = "string";

        var lbl = document.createElement("label");
        lbl.htmlFor = name;
        lbl.appendChild(document.createTextNode(name));

        if (opts.length > 0)
        {
            var datalist = document.createElement("datalist");
            datalist.id = method + "-" + name + "-data";
            for (const e of opts)
            {
                var o = document.createElement("option");
                o.value = e;
                datalist.appendChild(o);
            }
            pNode.appendChild(datalist);
            toggle.setAttribute("list", datalist.id);
        }
        iNode.appendChild(lbl);
        iNode.appendChild(toggle);
    }
    else if (type.startsWith("JSON"))
    {
        var toggle = document.createElement("textarea");
        toggle.type = "text";
        toggle.id = name;
        toggle.name = name;
        toggle.value_type = "JSON";

        var lbl = document.createElement("label");
        lbl.htmlFor = name;
        lbl.appendChild(document.createTextNode(name));

        iNode.appendChild(lbl);
        iNode.appendChild(toggle);
    }

    // Add functions to add input values.
    if (type.endsWith("*"))
    {
        var add = document.createElement("button");
        var rm = document.createElement("button");

        add.innerText = "Add";
        add.onclick = function() { addParam(this); };
        rm.innerText = "Remove";
        rm.onclick = function() { rmParam(this); };

        pNode.appendChild(document.createElement("label"));
        pNode.appendChild(add);
        pNode.appendChild(rm);
    }

    return pNode;
}

function addParam(btn)
{
    // The 'btn' is any of the input nodes in the parameter value, so remove
    // onfocus for all nodes in the parent to prevent this one from spawning
    // more children.
    let parent = btn.parentNode;
    let params = parent.querySelectorAll(".parameter");
    if (params.length > 0)
    {
        // Create and append clone to the parent.
        let clone = params[0].cloneNode(true);
        // clone.id = "something-new";
        parent.insertBefore(clone, params[0].nextSibling);
    }
}

function rmParam(btn)
{
    let parent = btn.parentNode;
    let params = parent.querySelectorAll(".parameter");
    if (params.length > 1)
    {
        // Create and append clone to the parent.
        // clone.id = "something-new";
        parent.removeChild(params[0]);
    }
}

function submitCameraMethod(method)
{
    // Collect all parameters, then call the appropriate method.
    let ep = method.endpoint;
    let method_fn = camera[ep][method.id];
    let params = method.querySelectorAll(".parameter input");

    var res = {};
    if (method.expects === "object")
    {
        // Expects a list of objects.
        let args = {};
        for (const p of params)
        {
            if (p.value)
            {
                args[p.id] = getParameterValue(p);
            }
        }
        res = method_fn([args]);
    }
    else if (method.expects == "list")
    {
        // Expects a list of arguments.
        let args = [];
        for (const p of params)
        {
            args.push(getParameterValue(p));
        }
        res = method_fn(args);
    }
    else
    {
        // Expects no parameters.
        res = method_fn();
    }

    log(method.id + ":");
    // call with args and present the results.
    if (camera.prettyfy)
    {
        log(JSON.stringify(res, null, 4));
    }
    else
    {
        log(JSON.stringify(res));
    }
}

function getParameterValue(p)
{
    if (p.value_type == "bool")
    {
        return p.checked;
    }
    else if (p.value_type == "int")
    {
        return parseInt(p.value);
    }
    else if (p.value_type == "double")
    {
        return parseFloat(p.value);
    }
    {
        return p.value;
    }
}
