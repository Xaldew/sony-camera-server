class Camera
{
    constructor()
    {
        this.server = {};
        this.status = null;
        this.prettyfy = true;
        this.endpoints = [];
        this.zooming = "idle";
        this.zoom_timeout_id = 0;
        this.color_temp_enabled = true;

        this.find_endpoints();
        this.find_methods();

        this.setup_base_ui();
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
        let methDiv = document.getElementById("raw-camera-methods");
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
                        let resp = JSON.parse(req.responseText);
                        console.log(resp);
                        return resp;
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

    setup_base_ui()
    {
        let res = this.camera.getEvent([false]);
        console.log(res);
        let events = res.result || [];
        if (events.length == 0)
        {
            return;
        }
        this.setup_camera_function(events);
        this.setup_shoot_modes(events);
        this.setup_actions(events);
        this.setup_settings(events);
        this.setup_status(events);
    }

    setup_camera_function(events)
    {
        // Camera function is available at index 12.
        if (events.length < 13 || events[12] === null)
        {
            return;
        }
        let fnNode = document.getElementById("camera-function");
        fnNode.textContent = "";
        let fns = events[12];
        for (const f of fns.cameraFunctionCandidates)
        {
            let div = document.createElement("div");
            let input = document.createElement("input");
            let txt = document.createTextNode(f);
            input.type = "radio";
            input.value = f;
            input.name = "camera-function-mode";
            if (f == fns.currentCameraFunction)
            {
                input.checked = true;
            }
            input.onchange = function(val)
            {
                log("Changing camera function: " + val.target.value);
                camera.camera.setCameraFunction([val.target.value]);
                // Wait for transition. This is unreliable though, so reload UI
                // again after a little while.
                camera.camera.getEvent([true]);
                camera.setup_base_ui();
                if (val.target.value == "Contents Transfer")
                {
                    setTimeout(function() { updateFileTree(); }, 5000);
                }
                setTimeout(function() { camera.setup_base_ui(); }, 2000);
            };
            div.appendChild(input);
            div.appendChild(txt);
            fnNode.appendChild(div);
        }
    }

    setup_shoot_modes(events)
    {
        // Shooting-mode is available at index 21 of getEvent().
        if (events.length < 22 || events[21] === null)
        {
            return;
        }
        let modeNode = document.getElementById("camera-shoot-mode");
        modeNode.textContent = "";

        let modes = events[21];
        for (const m of modes.shootModeCandidates)
        {
            let div = document.createElement("div");
            let input = document.createElement("input");
            let txt = document.createTextNode(m);
            input.type = "radio";
            input.value = m;
            input.name = "camera-shoot-mode";
            if (m == modes.currentShootMode)
            {
                input.checked = true;
            }
            input.onchange = function(val)
            {
                log("Changing shooting mode: " + val.target.value);
                camera.camera.setShootMode([val.target.value]);
                camera.setup_base_ui();
            };
            div.appendChild(input);
            div.appendChild(txt);
            modeNode.appendChild(div);
        }
    }

    setup_actions(events)
    {
        let actionNode = document.getElementById("camera-action");
        actionNode.textContent = "";

        let reload = document.createElement("input");
        reload.type = "button";
        reload.value = "Reload UI";
        reload.className = "action";
        reload.onclick = function() { camera.setup_base_ui(); };

        // Can't shoot while in contents transfer mode.
        if (events.length < 13 ||
            events[12] === null ||
            events[12].currentCameraFunction == "Contents Transfer")
        {
            actionNode.appendChild(reload);
            return;
        }

        // Focusing is available on index 35.
        if (events.length > 35 && events[35] !== null)
        {
            // Add Focus or cancel buttons depending on state.
            let focus = events[35];
            if (focus.focusStatus == "Focused")
            {
                let cancel = document.createElement("input");
                cancel.type = "button";
                cancel.value = "Cancel";
                cancel.className = "action";
                cancel.onclick = function()
                {
                    camera.camera.cancelHalfPressShutter();
                    camera.setup_base_ui();
                }
                actionNode.appendChild(cancel);
            }
            else
            {
                let startFocus = document.createElement("input");
                startFocus.type = "button";
                startFocus.value = "Focus";
                startFocus.className = "action";
                startFocus.onclick = function()
                {
                    camera.camera.actHalfPressShutter();
                    camera.setup_base_ui();
                }
                actionNode.appendChild(startFocus);
            }
        }
        if (events.length < 22 || events[21] === null)
        {
            actionNode.appendChild(reload);
            return;
        }

        // Add Shot/Stop buttons.
        let shootMode = events[21].currentShootMode;
        let status = events[1].cameraStatus;
        console.log(status);
        if (status == "IDLE" || status == "NotReady")
        {
            let shoot = document.createElement("input");
            shoot.type = "button";
            shoot.value = "Shoot";
            shoot.className = "action";
            shoot.onclick = function()
            {
                if (shootMode == "still")
                {
                    camera.camera.actTakePicture();
                    setTimeout(function() {camera.setup_base_ui();}, 2000);
                }
                else if (shootMode == "movie")
                {
                    camera.camera.startMovieRec();
                }
                else if (shootMode == "intervalstill")
                {
                    camera.camera.startIntervalStillRec();
                }
                else if (shootMode == "looprec")
                {
                    camera.camera.startLoopRec();
                }
                camera.setup_base_ui();
            };
            actionNode.appendChild(shoot);
        }
        else
        {
            let stop = document.createElement("input");
            stop.type = "button";
            stop.value = "Stop";
            stop.className = "action";
            stop.onclick = function()
            {
                if (shootMode == "movie")
                {
                    camera.camera.stopMovieRec();
                }
                else if (shootMode == "intervalstill")
                {
                    camera.camera.stopIntervalStillRec();
                }
                else if (shootMode == "looprec")
                {
                    camera.camera.stopLoopRec();
                }
                camera.setup_base_ui();
            };
            actionNode.appendChild(stop);
        }
        actionNode.appendChild(reload);

        // Add Zoom in/out buttons if supported.
        if (events.length >= 37 &&
            events[36] &&
            events[36].zoom.startsWith("On"))
        {
            let divIn = document.createElement("div");
            let divOut = document.createElement("div");

            if (this.zooming == "idle")
            {
                // If Idle, add both zoom in/out buttons.
                let zoomIn = document.createElement("input");
                zoomIn.type = "button";
                zoomIn.value = "Zoom In";
                zoomIn.onclick = function()
                {
                    camera.camera.actZoom(["in", "start"]);
                    camera.zooming = "in";
                    camera.zoom_timeout_id = setTimeout(function(){
                        camera.zooming = "idle";
                        camera.setup_base_ui();
                    }, 10000);
                    camera.setup_base_ui();
                };
                let zoomInStep = document.createElement("input");
                zoomInStep.type = "button";
                zoomInStep.value = "Zoom In Step";
                zoomInStep.onclick = function()
                {
                    camera.camera.actZoom(["in", "1shot"]);
                    camera.setup_base_ui();
                };
                divIn.appendChild(zoomIn);
                divIn.appendChild(zoomInStep);

                let zoomOut = document.createElement("input");
                zoomOut.type = "button";
                zoomOut.value = "Zoom Out";
                zoomOut.onclick = function()
                {
                    camera.camera.actZoom(["out", "start"]);
                    camera.zooming = "out";
                    camera.zoom_timeout_id = setTimeout(function(){
                        camera.zooming = "idle";
                        camera.setup_base_ui();
                    }, 10000);
                    camera.setup_base_ui();
                };
                let zoomOutStep = document.createElement("input");
                zoomOutStep.type = "button";
                zoomOutStep.value = "Zoom Out Step";
                zoomOutStep.onclick = function()
                {
                    camera.camera.actZoom(["out", "1shot"]);
                    camera.setup_base_ui();
                };
                divOut.appendChild(zoomOut);
                divOut.appendChild(zoomOutStep);
            }
            else if (this.zooming == "in")
            {
                // Currently zooming in, only add Zoom-in-stop button.
                let zoomStop = document.createElement("input");
                zoomStop.type = "button";
                zoomStop.value = "Zoom Stop";
                zoomStop.onclick = function()
                {
                    camera.camera.actZoom(["in", "stop"]);
                    camera.zooming = "idle";
                    clearTimeout(camera.zoom_timeout_id);
                    camera.setup_base_ui();
                };
                divIn.appendChild(zoomStop);
            }
            else if (this.zooming == "out")
            {
                // Currently zooming out, only add Zoom-out-stop button.
                let zoomStop = document.createElement("input");
                zoomStop.type = "button";
                zoomStop.value = "Zoom Stop";
                zoomStop.onclick = function()
                {
                    camera.camera.actZoom(["out", "stop"]);
                    camera.zooming = "idle";
                    clearTimeout(camera.zoom_timeout_id);
                    camera.setup_base_ui();
                };
                divIn.appendChild(zoomStop);
            }

            actionNode.appendChild(divIn);
            actionNode.appendChild(divOut);
        }
    }

    setup_status(events)
    {
        let stDiv = document.getElementById("camera-status");
        stDiv.textContent = "";

        let status = {
            0: "AvailableApiList",
            1: "Camera Status",
            2: "Zoom Information",
            3: "LiveviewStatus",
            5: "PictureURLs",
            6: "Warnings",
            7: "Errors",
            10: "StorageInfo",
            56: "BatteryInfo",
            58: "Number Of Shots",
            73: "temporarilyUnavailableApiList",
            76: "GPS Status",
        };

        for (let [k, v] of Object.entries(status))
        {
            if (events.length > k + 1 && events[k])
            {
                let e = events[k];
                let hdr = document.createTextNode(v);
                let li = createListDescription(hdr, e);
                stDiv.appendChild(li);
            }
        }
    }

    setup_settings(events)
    {
        let setDiv = document.getElementById("camera-settings");
        setDiv.textContent = "";

        for (const e of events)
        {
            if (typeof e !== 'object' || Array.isArray(e) || e === null)
            {
                continue;
            }
            // Skip this, it is listed elsewhere.
            if (e.type == "cameraFunction" || e.type == "shootMode")
            {
                continue;
            }
            let cands = e[e.type + "Candidates"] || e["candidate"];
            if (typeof cands == "undefined" || cands.length == 0)
            {
                continue;
            }
            // The consequences of not sticking to a standard scheme...
            let type_upcase = e.type.charAt(0).toUpperCase() + e.type.slice(1);
            let current = tryGetValue(e[e.type],
                                      e["current" + type_upcase],
                                      e["zoom"],
                                      e["flip"],
                                      e["scene"],
                                      "")
            let key = firstAvailableKey(e, e.type, "zoom", "flip", "scene");
            var type = typeof current;
            if (type != "string" && type != "number" && type != "boolean")
            {
                type = "string";
            }

            let mNode = document.createElement("div");
            mNode.id = e.type;
            mNode.className = "camera-setting";
            setDiv.appendChild(mNode);

            var lbl = document.createElement("label");
            lbl.htmlFor = e.type;
            lbl.appendChild(document.createTextNode(e.type));

            if (cands.length > 0)
            {
                var list = document.createElement("select");
                list.id = e.type;
                list.name = e.type;
                list.key = key;
                list.value_type = type;
                list.className = "camera-setting";
                list.onchange = function(setting)
                {
                    // Key == undefined is a possible way of detecting
                    // array/object expected arguments.
                    let set = setting.target.name;
                    let fn = "set" + set.charAt(0).toUpperCase() + set.slice(1);
                    let methodNode = document.getElementById(fn);
                    let exp = "list";
                    if (methodNode)
                    {
                        exp = methodNode.expects || exp;
                    }
                    let val = getParameterValue(setting.target);
                    if (exp == "list")
                    {
                        camera.camera[fn]([val]);
                    }
                    else
                    {
                        let p = {};
                        p[setting.target.key] = val;
                        camera.camera[fn]([p]);
                    }
                    camera.setup_base_ui();
                };
                for (const can of cands)
                {
                    var opt = document.createElement("option");
                    opt.value = can;
                    opt.innerText = can;
                    if (current == can)
                    {
                        opt.selected = true;
                    }
                    list.appendChild(opt);
                }
                mNode.appendChild(lbl);
                mNode.appendChild(list);
            }
            else if (type == "boolean")
            {
                // Create a check-box.
                var toggle = document.createElement("input");
                toggle.type = "checkbox";
                toggle.id = e.type;
                toggle.name = e.type;
                toggle.checked = current;
                toggle.onchange = function(setting)
                {
                    let set = setting.target.name;
                    let fn = "set" + set.charAt(0).toUpperCase() + set.slice(1);
                    let val = getParameterValue(setting.target);
                    camera.camera[fn]([val]);
                    camera.setup_base_ui();
                };
                mNode.appendChild(lbl);
                mNode.appendChild(toggle);
            }
        }
        if (events.length > 34 && events[33])
        {
            // Add whitebalance settings.
            let wb = events[33];
            let curTemp = wb.currentColorTemperature
            let curWbMode = wb.currentWhiteBalanceMode;
            if (wb.checkAvailability)
            {
                let mNode = document.createElement("div");
                mNode.className = "camera-setting";

                let result = this.camera.getAvailableWhiteBalance();
                let res = result.result;
                if (res)
                {
                    var modes = [];
                    var temps = [];
                    for (const obj of res[1])
                    {
                        modes.push(obj.whiteBalanceMode);
                        if (obj.whiteBalanceMode == curWbMode)
                        {
                            let tempStart = obj.colorTemperatureRange[1];
                            let tempEnd = obj.colorTemperatureRange[0];
                            let tempStep = obj.colorTemperatureRange[2];
                            for (var i = tempStart; i <= tempEnd; i += tempStep)
                            {
                                temps.push(i);
                            }
                        }
                    }

                    var modeLabel = document.createElement("label");
                    modeLabel.htmlFor = "WhiteBalanceMode";
                    modeLabel.appendChild(document.createTextNode("WhiteBalanceMode"));

                    var modeList = document.createElement("select");
                    modeList.id = "WhiteBalanceMode";
                    modeList.name = "WhiteBalanceMode";
                    modeList.value_type = "string";
                    modeList.className = "camera-setting";
                    modeList.onchange = function(setting) {
                        let set = setting.target.name;
                        let val = getParameterValue(setting.target);
                        let enabled = camera.color_temp_enabled;
                        camera.camera.setWhiteBalance([val, enabled, -1]);
                        camera.setup_base_ui();
                    };
                    for (const v of modes)
                    {
                        let opt = document.createElement("option");
                        opt.value = v;
                        opt.innerText = v;
                        if (curWbMode == v)
                        {
                            opt.selected = true;
                        }
                        modeList.appendChild(opt);
                    }
                    mNode.appendChild(modeLabel);
                    mNode.appendChild(modeList);
                    setDiv.appendChild(mNode);

                    let eNode = document.createElement("div");
                    eNode.className = "camera-setting";

                    var enableLabel = document.createElement("label");
                    enableLabel.htmlFor = "ColorTemperatureEnable";
                    enableLabel.appendChild(document.createTextNode("ColorTemperatureEnable"));
                    var enableList = document.createElement("select");
                    enableList.id = "ColorTemperatureEnable";
                    enableList.name = "ColorTemperatureEnable";
                    enableList.value_type = "boolean";
                    enableList.className = "camera-setting";
                    enableList.onchange = function(setting) {
                        let set = setting.target.name;
                        let val = setting.target.value === "true";
                        camera.color_temp_enabled = val;
                        camera.camera.setWhiteBalance([curWbMode, val, curTemp]);
                        camera.setup_base_ui();
                    };
                    let onOpt = document.createElement("option");
                    onOpt.value = true;
                    onOpt.innerText = "On";
                    if (this.color_temp_enabled)
                    {
                        onOpt.selected = true;
                    }
                    enableList.appendChild(onOpt);
                    let offOpt = document.createElement("option");
                    offOpt.value = false;
                    offOpt.innerText = "Off";
                    if (!this.color_temp_enabled)
                    {
                        offOpt.selected = true;
                    }
                    enableList.appendChild(offOpt);
                    eNode.appendChild(enableLabel);
                    eNode.appendChild(enableList);
                    setDiv.appendChild(eNode);

                    if (temps.length > 0)
                    {
                        let tNode = document.createElement("div");
                        tNode.className = "camera-setting";
                        var tempLabel = document.createElement("label");
                        tempLabel.htmlFor = "WhiteBalanceTemperature";
                        tempLabel.appendChild(document.createTextNode("WhiteBalanceTemperature"));

                        var tempList = document.createElement("select");
                        tempList.id = "WhiteBalanceTemperature";
                        tempList.name = "WhiteBalanceTemperature";
                        tempList.value_type = "number";
                        tempList.className = "camera-setting";
                        tempList.onchange = function(setting) {
                            let set = setting.target.name;
                            let val = getParameterValue(setting.target);
                            let enabled = camera.color_temp_enabled;
                            camera.camera.setWhiteBalance([curWbMode, enabled, val]);
                            camera.setup_base_ui();
                        };
                        for (const t of temps)
                        {
                            let opt = document.createElement("option");
                            opt.value = t;
                            opt.innerText = t;
                            if (curTemp == t)
                            {
                                opt.selected = true;
                            }
                            tempList.appendChild(opt);
                        }

                        tNode.appendChild(tempLabel);
                        tNode.appendChild(tempList);
                        setDiv.appendChild(tNode);
                    }
                }
            }
        }
        if (events.length > 26 && events[25])
        {
            // Add ExposureCompensation settings.
            let e = events[25];
            let exps = {}
            let min = e.minExposureCompensation;
            let max = e.maxExposureCompensation;
            let step = e.stepIndexOfExposureCompensation;
            for (var i = min; i < max + 1; i += step)
            {
                exps[i] = true;
            }
            let current = e.currentExposureCompensation;

            let mNode = document.createElement("div");
            mNode.id = e.type;
            mNode.className = "camera-setting";
            setDiv.appendChild(mNode);

            var lbl = document.createElement("label");
            lbl.htmlFor = e.type;
            lbl.appendChild(document.createTextNode(e.type));

            var list = document.createElement("select");
            list.id = e.type;
            list.name = e.type;
            list.value_type = "number";
            list.className = "camera-setting";
            list.onchange = function(setting)
            {
                let val = getParameterValue(setting.target);
                camera.camera.setExposureCompensation([val]);
                camera.setup_base_ui();
            };
            let keys = Object.keys(exps);
            keys.sort();
            for (const can of keys)
            {
                var opt = document.createElement("option");
                opt.value = can;
                opt.innerText = can;
                if (current == can)
                {
                    opt.selected = true;
                }
                list.appendChild(opt);
            }
            mNode.appendChild(lbl);
            mNode.appendChild(list);
        }
    }
}

function init()
{
    refreshDevices();
}

function tryGetValue()
{
    for (var i = 0; i < arguments.length; i++)
    {
        let val = arguments[i];
        if (val !== undefined && val !== null)
            return val;
    }
}

function firstAvailableKey()
{
    if (arguments.length == 0 || arguments.length == 1 ||
        (typeof arguments[0]  !== 'object' || arguments[0] === null))
    {
        return undefined;
    }
    let obj = arguments[0];
    for (var i = 1; i < arguments.length; i++)
    {
        if (arguments[i] in obj)
            return arguments[i];
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
        d_sp.onclick = function() {
            this.parentElement.querySelector(".nested").classList.toggle("active");
            this.classList.toggle("caret-down");
        };
        let f_ul = document.createElement("ul");
        f_ul.className = "nested";
        let files = listFromUri(d.uri, /.*/g);
        for (const f of files)
        {
            let fa = document.createElement("a");
            fa.href = "/" + f.uri;
            fa.target="_blank";
            fa.rel="noopener noreferrer";
            fa.innerText = f.uri;
            let f_li = createListDescription(fa, f);
            f_ul.appendChild(f_li);
        }
        d_li.appendChild(d_sp);
        d_li.appendChild(f_ul);
        tree.appendChild(d_li);
    }
}

function createListDescription(hdr, info)
{
    let li = document.createElement("li");
    let sp = document.createElement("span");
    sp.className = "caret";
    sp.onclick = function() {
        this.parentElement.querySelector(".nested").classList.toggle("active");
        this.classList.toggle("caret-down");
    };
    let ul = document.createElement("ul");
    ul.className = "nested";
    for (let [k, v] of Object.entries(info))
    {
        if (typeof v === 'object' && v !== null)
        {
            let tn = document.createTextNode(k);
            let i = createListDescription(tn, v);
            ul.appendChild(i);
        }
        // else if (Array.isArray(v))
        // {
        // }
        else
        {
            let i = document.createElement("li");
            let s = document.createElement("span");
            s.innerText = k + ": ";
            i.appendChild(s);
            if (typeof v == "string" && v.startsWith("http"))
            {
                let a = document.createElement("a");
                a.target="_blank";
                a.rel="noopener noreferrer";
                a.href = v;
                a.innerText = v;
                i.appendChild(a);
            }
            else
            {
                let txt = document.createTextNode(v);
                i.appendChild(txt);
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
    if (p.value_type == "bool" || p.value_type == "boolean")
    {
        return p.checked;
    }
    else if (p.value_type == "int")
    {
        return parseInt(p.value);
    }
    else if (p.value_type == "double" || p.value_type == "number")
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
