<resource schema="ccd_observations">
  <service id="zeroed" allowed="qp">
    <meta name="shortName">FAI safe FITS download</meta>
    <meta name="title">Download an FAI CCD FITS product safely</meta>
    <property name="queryField">product</property>
    <pythonCore>
      <inputTable>
        <inputKey name="product" type="text" required="True"/>
      </inputTable>
      <coreProc>
        <setup imports="datetime, io, os, re">
          <code><![CDATA[
            from astropy.io import fits
            from gavo import svcs

            ZERO_CHUNK = b"\0"*(1024*1024)
            MAX_PRODUCT_SIZE = 512*1024*1024
            PRODUCT_PREFIX = "ccd_observations/products/"

            def writeZeros(dest, byteCount):
              while byteCount:
                chunkSize = min(byteCount, len(ZERO_CHUNK))
                dest.write(ZERO_CHUNK[:chunkSize])
                byteCount -= chunkSize

            def makeZeroDataFITS(sourcePath):
              sourceSize = os.path.getsize(sourcePath)
              if sourceSize > MAX_PRODUCT_SIZE:
                raise svcs.Error("FITS product is too large for safe delivery")

              # Astropy reads the HDU layout but leaves image arrays on disk.
              # fileinfo then lets us copy header blocks exactly while never
              # reading the proprietary data bytes.
              with fits.open(sourcePath, mode="readonly", memmap=True,
                  do_not_scale_image_data=True,
                  lazy_load_hdus=False) as hdus:
                infos = [hdus.fileinfo(index)
                  for index in range(len(hdus))]

              result = io.BytesIO()
              cursor = 0
              with open(sourcePath, "rb") as source:
                for info in infos:
                  headerStart = int(info["hdrLoc"])
                  dataStart = int(info["datLoc"])
                  dataSpan = int(info["datSpan"])
                  if headerStart != cursor or dataStart < headerStart:
                    raise svcs.Error("Unexpected FITS block layout")

                  source.seek(headerStart)
                  header = source.read(dataStart-headerStart)
                  if len(header) != dataStart-headerStart:
                    raise svcs.Error("Truncated FITS header")
                  result.write(header)
                  writeZeros(result, dataSpan)
                  cursor = dataStart+dataSpan

              # Do not copy non-HDU trailing bytes; zero them as well so no
              # unparsed source content can leak into the public response.
              if cursor > sourceSize:
                raise svcs.Error("Invalid FITS data span")
              writeZeros(result, sourceSize-cursor)
              return result.getvalue()
          ]]></code>
        </setup>
        <code><![CDATA[
          requestPath = str(inputTable.getParam("product") or "")
          pathParts = requestPath.split("/", 1)
          if (len(pathParts) != 2
              or not re.fullmatch(r"[0-9a-f]{64}", pathParts[0])):
            raise svcs.UnknownURI("Invalid CCD product identifier")

          accref = PRODUCT_PREFIX+pathParts[0]+".fits"
          with base.getTableConn() as conn:
            rows = list(conn.query(
              "SELECT accesspath, embargo FROM dc.products "
              "WHERE accref=%(accref)s "
              "AND sourcetable='ccd_observations.main' "
              "AND mime='application/fits'",
              {"accref": accref}))
          if len(rows) != 1:
            raise svcs.UnknownURI("No such CCD product")

          accessPath, embargo = rows[0]
          sourcePath = os.path.realpath(os.path.join(
            str(base.getConfig("inputsDir")), accessPath))
          inputsRoot = os.path.realpath(str(base.getConfig("inputsDir")))
          if os.path.commonpath([inputsRoot, sourcePath]) != inputsRoot:
            raise svcs.UnknownURI("Unsafe CCD product path")
          if os.path.basename(sourcePath) != pathParts[1]:
            raise svcs.UnknownURI("CCD product name does not match")
          if not os.path.isfile(sourcePath):
            raise svcs.UnknownURI("CCD product file is unavailable")

          if embargo is not None and embargo > datetime.date.today():
            payload = makeZeroDataFITS(sourcePath)
          else:
            with open(sourcePath, "rb") as source:
              payload = source.read()
          return "application/fits", payload
        ]]></code>
      </coreProc>
    </pythonCore>
  </service>
</resource>
