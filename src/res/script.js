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
            this.endpoints = res["result"] || {};
            console.log(this.endpoints);
        }
    }

    find_methods()
    {
        let methDiv = document.getElementById("camera-methods");
        methDiv.textContent = "";

        for (let [epName, methods] of Object.entries(this.endpoints))
        {
            this[epName] = {};
            let epNode = document.createElement("div");
            epNode.id = epName;
            epNode.className = "camera-endpoint";
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
    refreshDevices();
}

function enableListNesting()
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
            let result = JSON.parse(this.response);
            let devices = result["result"];
            updateDeviceList(devices);
            // If there's only one device, set it.
            if (devices.length == 1)
            {
                changeDevice();
            }
        }
    };
}

function changeDevice()
{
    let devs = document.getElementById("device-select");
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "server", true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onreadystatechange = function()
    {
        if (this.readyState === XMLHttpRequest.DONE && this.status === 200)
        {
            log("Device change successful");
            camera = new Camera();
            console.log(camera);
        }
    };
    xhr.send(JSON.stringify({
        method: "changeDevice",
        params: [{device: devs.value}],
    }));
}

function updateDeviceList(devices)
{
    let devicesNode = document.getElementById("device-select");

    // Delete old list.
    while (devicesNode.firstChild)
    {
        devicesNode.removeChild(devicesNode.lastChild);
    }

    // If empty, just insert a no-option value.
    if (devices.length == 0)
    {
        let node = document.createElement("option");
        node.innerText = "no-device";
        devicesNode.appendChild(node);
        return;
    }

    let dev_value = devicesNode.value;
    let in_list = false;

    for (var i = 0; i < devices.length; i++)
    {
        let node = document.createElement("option");
        node.innerText = devices[i];
        if (devices[i] == dev_value)
        {
            in_list = true;
        }
        devicesNode.appendChild(node);
    }
    // Make sure that if the original is in the list, keep it selected.
    if (in_list)
    {
        devicesNode.value = dev_value;
    }
}

function reloadLiveview()
{
    // Ask server to start the liveview.
    camera.camera.startLiveview();

    // Ask browser to reload the liveview element.
    let lv = document.getElementById("liveview");
    let content = lv.innerHTML;
    lv.innerHTML = content;
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
            let code = result.result || [-1];
            if (input.value == "contents" // && code[0] === 0
               )
            {
                updateFileTree();
            }
        }
    };
    xhr.send(JSON.stringify(value));
}

function updateFileTree()
{
    log("Starting rebuild of file-tree...");
    let tree = document.getElementById("filetree");
    tree.textContent = ""; // Clear node.

    let res = camera.avContent.getSchemeList();
    let schemes = (res.result || [[]]);
    let srcs = getStorageSources(schemes);
    let directories = getDirectories(srcs);
    for (const d of directories)
    {
        let d_li = document.createElement("li");
        let d_sp = document.createElement("span");
        d_sp.className = "caret";
        d_sp.innerText = d.title;
        let f_ul = document.createElement("ul");
        f_ul.className = "nested";
        let files = listFromUri(d.uri, /.*/g);
        for (const f of files)
        {
            let fa = document.createElement("a");
            fa.href = "/" + f.uri;
            fa.innerText = f.uri;
            let f_li = createFileDescription(fa, f);
            f_ul.appendChild(f_li);
        }
        d_li.appendChild(d_sp);
        d_li.appendChild(f_ul);
        tree.appendChild(d_li);
    }
    // let files = getFiles(directories);
    enableListNesting();
}

function createFileDescription(hdr, file_info)
{
    let li = document.createElement("li");
    let sp = document.createElement("span");
    sp.className = "caret";
    let ul = document.createElement("ul");
    ul.className = "nested";
    for (let [k, v] of Object.entries(file_info))
    {
        if (typeof v === 'object' && v !== null)
        {
            let tn = document.createTextNode(k);
            let i = createFileDescription(tn, v);
            ul.appendChild(i);
        }
        else
        {
            let i = document.createElement("li");
            let s = document.createElement("span");
            s.innerText = k + ": ";
            i.appendChild(s);
            if (v.startsWith("http"))
            {
                let a = document.createElement("a");
                a.href = v;
                a.innerText = v;
                i.appendChild(a);
            }
            else
            {
                i.innerText = v;
            }
            ul.appendChild(i);
        }
    }
    li.append(sp);
    li.appendChild(hdr);
    li.appendChild(ul);
    return li;
}



function getStorageSources(schemes)
{
    let srcs = [];
    for (const sch of schemes)
    {
        let res = camera.avContent.getSourceList(sch);
        let storage = res.result || [[]];
        for (const s of storage[0])
        {
            srcs.push(s.source);
        }
    }
    return srcs;
}

function listFromUri(uri, type)
{
    var files = [];
    let p = {uri: uri, view: "date"};
    let result = camera.avContent.getContentCount([p]);
    let res = result.result || [{count:0}];
    let cnt = res[0].count;
    let iters = (cnt > 0) + Math.floor(cnt / 100);
    for (var i = 0; i < iters; i++)
    {
        let c = {uri: uri, stIdx: i * 100, cnt: 100, view: "date"};
        let cresult = camera.avContent.getContentList([c]);
        let content = cresult.result || [[]];
        for (const f of content[0])
        {
            let match = f.contentKind.match(type);
            if (match !== null)
            {
                files.push(f);
            }
        }
    }
    return files;
}

function getDirectories(srcs)
{
    let dirs = [];
    for (const s of srcs)
    {
        let d = listFromUri(s, /directory/g);
        dirs = dirs.concat(d);
    }
    return dirs;
}

function getFiles(dirs)
{
    let files = [];
    for (const d of dirs)
    {
        let f = listFromUri(d.uri, /.*/g);
        files = files.concat(f);
    }
    return files;
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
    else if (p.value_type == "JSON")
    {
        try
        {
            return JSON.parse(p.value);
        }
        catch (e)
        {
            return p.value;
        }
    }
    else
    {
        return p.value;
    }
}
